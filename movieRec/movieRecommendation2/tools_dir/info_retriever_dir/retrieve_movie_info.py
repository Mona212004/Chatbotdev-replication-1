import re
import time
import logging
import os
import psycopg2
from dotenv import load_dotenv
from pathlib import Path
from tavily import TavilyClient
from movieRec.config import load_config

# Load env so TAVILY_API_KEY is available when running on Render
load_dotenv(dotenv_path=Path(__file__).resolve().parent / ".env")
TAVILY_API_KEY = os.getenv("TAVILY_API_KEY")


# ── Shared extraction helpers (open-web Tavily fallback) ──────────────────────


def _clean_web_text(raw: str) -> str:
    """Strip HTML tags and collapse whitespace."""
    text = re.sub(r"<[^>]+>", " ", raw)
    return re.sub(r"\s+", " ", text).strip()


def _extract_field(text: str, patterns: list) -> str:
    """Try each regex pattern in order, return first match or empty string."""
    for pattern, fmt in patterns:
        m = re.search(pattern, text, re.IGNORECASE)
        if m:
            return fmt(m)
    return ""


def _extract_genres_from_text(text: str) -> str:
    genre_keywords = [
        "action",
        "adventure",
        "animation",
        "comedy",
        "crime",
        "documentary",
        "drama",
        "fantasy",
        "horror",
        "mystery",
        "romance",
        "sci-fi",
        "science fiction",
        "thriller",
        "western",
        "musical",
        "family",
        "biography",
        "history",
        "sport",
        "war",
    ]
    found = [g for g in genre_keywords if g in text.lower()]
    return ", ".join(found) if found else "N/A"


def _extract_duration_from_text(text: str) -> str:
    result = _extract_field(
        text,
        [
            (
                r"(\d+)\s*h(?:r|our)?s?\s*(\d+)\s*m(?:in)?",
                lambda m: f"{m.group(1)}h {m.group(2)}min",
            ),
            (r"(?<!\d)(\d{1,2})(?!\d)\s*h(?:r|our)?s?", lambda m: f"{m.group(1)}h"),
            (
                r"(?<!\d)(\d{2,3})(?!\d)\s*m(?:in(?:ute)?s?)?",
                lambda m: f"{m.group(1)}min",
            ),
        ],
    )
    return result or "N/A"


def _extract_rating_from_text(text: str) -> str:
    result = _extract_field(
        text,
        [
            (r"(\d+\.?\d*)\s*/\s*10", lambda m: m.group(1)),
            (r"(\d+\.?\d*)\s*out\s*of\s*10", lambda m: m.group(1)),
            (r"imdb[^\d]*(\d+\.?\d*)", lambda m: m.group(1)),
            (r"rating[:\s]+(\d+\.?\d*)", lambda m: m.group(1)),
        ],
    )
    if result:
        try:
            val = float(result)
            if 1.0 <= val <= 10.0:
                return str(round(val, 1))
        except ValueError:
            pass
    return "N/A"


def _extract_original_title(text: str, primary_title: str) -> str:
    m = re.search(
        r"(?:original(?:ly)?\s+(?:titled?|title\s*:)|also\s+known\s+as)\s*[\"']?([^\"'\n,]{3,60})[\"']?",
        text,
        re.IGNORECASE,
    )
    if m:
        candidate = m.group(1).strip().rstrip(".,")
        if candidate.lower() != primary_title.lower():
            return candidate
    return primary_title


def _truncate_at_sentence(text: str, char_limit: int = 400) -> str:
    """Truncate at sentence boundary rather than mid-sentence."""
    if len(text) <= char_limit:
        return text
    sentences = re.split(r"(?<=[.!?])\s+", text.strip())
    result = ""
    for s in sentences:
        candidate = (result + " " + s).strip() if result else s
        if len(candidate) <= char_limit:
            result = candidate
        else:
            break
    return result or text[:char_limit]


def _strip_attribution(text: str) -> str:
    """Remove 'Written by X', bylines, and boilerplate from plot text."""
    text = re.sub(r"(?i)(?:written|reviewed?|edited?)\s+by\s+[\w\s]{2,40}", "", text)
    text = re.sub(
        r"[\u2014\u2013-]\s*[A-Z][a-z]+(?:\s+[A-Z][a-z]+)+\s*$",
        "",
        text,
        flags=re.MULTILINE,
    )
    lines = [
        l
        for l in text.split("\n")
        if len(l.strip()) > 40 or (l.strip() and not l.strip().isupper())
    ]
    return " ".join(lines).strip()


def _fetch_movie_info_via_tavily(movie_title: str) -> dict:
    """
    Fetches movie metadata from the open web via Tavily.
    Returns a dict with keys: title, original_title, genres, rating,
    plot_summary, duration. Returns None if fetch fails.
    """
    if not TAVILY_API_KEY:
        print("[Tavily] TAVILY_API_KEY not set — skipping web fallback.")
        return None
    try:
        client = TavilyClient(api_key=TAVILY_API_KEY)
        response = client.search(
            query=f'"{movie_title}" plot summary genres runtime rating cast',
            search_depth="advanced",
            max_results=3,
            include_raw_content=True,
        )
        if not response or "results" not in response:
            return None

        for res in response["results"]:
            # Prefer Tavily's pre-extracted content snippet (already stripped of
            # nav/menus/logos). Only fall back to raw_content if too short.
            snippet = res.get("content", "")
            raw_full = res.get("raw_content", "")
            raw = snippet if snippet and len(snippet) > 150 else (raw_full or snippet)
            if not raw:
                continue
            cleaned = _clean_web_text(raw)
            plot_raw = _strip_attribution(cleaned)
            plot_summary = _truncate_at_sentence(plot_raw, char_limit=400)
            if not plot_summary:
                continue

            return {
                "title": movie_title,
                "original_title": _extract_original_title(cleaned, movie_title),
                "genres": _extract_genres_from_text(cleaned),
                "rating": _extract_rating_from_text(cleaned),
                "duration": _extract_duration_from_text(cleaned),
                "plot_summary": plot_summary,
            }
    except Exception as e:
        print(f"[Tavily] get_movie_info fetch failed for '{movie_title}': {e}")
    return None


def get_movie_info(movie_title: str) -> str:
    """
    Gets movie information from the local database given a movie title.
    Falls back to Tavily web search when plot is missing or title not in DB.
    """
    print(f"--- Tool: get_movie_info tool called with movie_title: {movie_title} ---")
    start_time = time.perf_counter()

    # 1. Execute Local Database Retrieval
    rows = []
    config = load_config()
    try:
        if isinstance(config, str):
            conn = psycopg2.connect(config)
        else:
            conn = psycopg2.connect(**config)

        with conn:
            with conn.cursor() as cursor:
                query = """
                    SELECT primarytitle, genres, averagerating, plot_summary, duration, plot_synopsis
                    FROM cleaned_imdb
                    WHERE primarytitle ILIKE %s
                    ORDER BY averagerating DESC NULLS LAST
                    LIMIT 3;
                """
                cursor.execute(query, (f"%{movie_title}%",))
                rows = cursor.fetchall()
        conn.close()
    except Exception as db_err:
        logging.getLogger(__name__).error(f"Database transaction failure: {db_err}")

    # 2. Compile result block
    local_candidates_block = ""
    if rows:
        for idx, row in enumerate(rows, 1):
            title, genres, rating, summary, duration, synopsis = row

            # Strip "Written by X" attribution from raw IMDB plot text
            clean_summary_raw = (
                re.sub(
                    r"\s*Written\s+by\s+[\w\s]*$",
                    "",
                    summary or "",
                    flags=re.IGNORECASE,
                ).strip()
                if summary
                else ""
            )
            clean_synopsis_raw = (
                re.sub(
                    r"\s*Written\s+by\s+[\w\s]*$",
                    "",
                    synopsis or "",
                    flags=re.IGNORECASE,
                ).strip()
                if synopsis
                else ""
            )

            # If DB plot is missing, fall back to Tavily for this candidate
            if not clean_summary_raw:
                print(f"--- Plot missing for '{title}' — fetching via Tavily ---")
                web_info = _fetch_movie_info_via_tavily(title)
                if web_info:
                    clean_summary_raw = web_info["plot_summary"]
                    if not genres:
                        genres = web_info["genres"]
                    if rating is None:
                        rating = web_info["rating"]
                    if not duration:
                        duration = web_info["duration"]

            clean_summary = (
                (clean_summary_raw[:250] + "...")
                if clean_summary_raw and len(clean_summary_raw) > 250
                else (clean_summary_raw or "N/A")
            )
            clean_synopsis = (
                (clean_synopsis_raw[:400] + "...")
                if clean_synopsis_raw and len(clean_synopsis_raw) > 400
                else (clean_synopsis_raw or "N/A")
            )

            local_candidates_block += (
                f"\nCandidate #{idx}: '{title}'\n"
                f"- Genres: {genres} | Rating: {rating} | Duration: {duration}\n"
                f"- Plot Summary: {clean_summary}\n"
                f"- Plot Synopsis: {clean_synopsis}\n"
            )

    # If nothing in DB at all, search the open web
    if not local_candidates_block:
        print(f"--- '{movie_title}' not in local database — fetching via Tavily ---")
        web_info = _fetch_movie_info_via_tavily(movie_title)
        if web_info:
            local_candidates_block = (
                f"\nCandidate #1: '{web_info['title']}' (via web search)\n"
                f"- Genres: {web_info['genres']} | Rating: {web_info['rating']} | Duration: {web_info['duration']}\n"
                f"- Plot Summary: {web_info['plot_summary']}\n"
            )
        else:
            local_candidates_block = (
                f"\n⚠️ NOTICE: No information found for '{movie_title}' "
                f"in the local database or via web search."
            )

    logging.getLogger(__name__).info(
        "`get_movie_info` executed successfully in %.3f ms",
        (time.perf_counter() - start_time) * 1000,
    )
    return local_candidates_block


if __name__ == "__main__":
    test_title = "The Addams Family"
    info = get_movie_info(test_title)
    print(info)
