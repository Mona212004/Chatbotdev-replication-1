import re
import time
import logging
import json
import numpy as np
import psycopg2
from typing import Optional, Any, List
import os
import warnings
from pathlib import Path
from dotenv import load_dotenv
from tavily import TavilyClient

from movieRec.config import load_config
from movieRec.movieRecommendation2.sharedLibraries.user_query_to_vector import (
    query_to_vectors,
)
from movieRec.movieRecommendation2.entities.user2 import UserFunctions

# Load Tavily API key the same way find_movie_tool.py does
current_file_path = Path(__file__).resolve()
project_root_dir = current_file_path.parent.parent.parent
env_path = project_root_dir / ".env"
load_dotenv(dotenv_path=env_path)
TAVILY_API_KEY = os.getenv("TAVILY_API_KEY")

func = UserFunctions()


# ── Tavily helpers ─────────────────────────────────────────────────────────────


def _clean_web_text(text: str) -> str:
    """Strips HTML tags and collapses whitespace from raw web content (from find_movie_tool.py)."""
    if not text:
        return "N/A"
    text = re.sub(r"<script\b[^<]*?>([\s\S]*?)</script>", "", text)
    text = re.sub(r"<style\b[^<]*?>([\s\S]*?)</style>", "", text)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def _extract_duration(text: str) -> str:
    """Extracts runtime from raw web text. Returns e.g. '1h 55m' or '' if not found."""
    patterns = [
        (
            r"(\d+)\s*h(?:r|our)?s?\s*(\d+)\s*m(?:in)?",
            lambda m: f"{m.group(1)}h {m.group(2)}m",
        ),
        (r"(\d+)\s*h(?:r|our)?s?", lambda m: f"{m.group(1)}h"),
        (r"(\d{2,3})\s*m(?:in(?:ute)?s?)?", lambda m: f"{m.group(1)}m"),
    ]
    text_lower = text.lower()
    for pattern, fmt in patterns:
        match = re.search(pattern, text_lower)
        if match:
            return fmt(match)
    return ""


def _extract_rating(text: str) -> str:
    """Extracts a /10 rating from raw web text. Returns e.g. '7.5' or 'N/A'."""
    patterns = [
        r"(\d+\.?\d*)\s*/\s*10",
        r"(\d+\.?\d*)\s*out\s*of\s*10",
        r"imdb[^\d]*(\d+\.?\d*)",
        r"rating[:\s]+(\d+\.?\d*)",
    ]
    text_lower = text.lower()
    for pattern in patterns:
        match = re.search(pattern, text_lower)
        if match:
            try:
                val = float(match.group(1))
                if 1.0 <= val <= 10.0:
                    return f"{val:.1f}"
            except ValueError:
                continue
    return "N/A"


def _extract_plot_text(raw_text: str) -> str:
    """
    Strips reviewer attribution, navigation boilerplate, and cast/crew bylines
    from raw web content, returning only plot-relevant sentences.
    """
    # Remove "Written by X", "Reviewed by X", "By X" attribution lines
    raw_text = re.sub(
        r"(?i)(?:written|reviewed?|contributed?|edited?|summarized?)\s+by\s+[A-Z][a-zA-Z\s]{2,40}",
        "",
        raw_text,
    )
    # Remove trailing em-dash bylines: "— John Smith" or "- Jane Doe"
    raw_text = re.sub(
        r"[\u2014\u2013-]\s*[A-Z][a-z]+(?:\s+[A-Z][a-z]+)+\s*$",
        "",
        raw_text,
        flags=re.MULTILINE,
    )
    # Remove lines that are purely navigation/metadata (very short or all-caps)
    lines = raw_text.split("\n")
    lines = [
        l
        for l in lines
        if len(l.strip()) > 40 or (l.strip() and not l.strip().isupper())
    ]
    return " ".join(lines)[:800].strip()


def _fetch_context_string_via_tavily(movie_title: str) -> Optional[str]:
    """
    Fetches plot, genre, duration and rating for any title (movie, TV series,
    documentary) from the open web via Tavily — not restricted to IMDB.
    Formats the result into the exact same context string structure used when
    DB embeddings were created (csv_batch_to_documents.py), so the generated
    embedding lands in the same vector space as existing DB rows.
    Returns None if the fetch fails or returns no usable content.
    """
    if not TAVILY_API_KEY:
        print("[Tavily] TAVILY_API_KEY not found in environment.")
        return None
    try:
        tavily_client = TavilyClient(api_key=TAVILY_API_KEY)

        # Open-web query — no site restriction so recent TV series, documentaries,
        # and titles missing from IMDB are found on Wikipedia, streaming sites, etc.
        refined_query = f'"{movie_title}" film plot summary synopsis genres runtime rating'

        search_response = tavily_client.search(
            query=refined_query,
            search_depth="advanced",
            max_results=3,
            include_raw_content=True,
        )
        if not search_response or "results" not in search_response:
            return None

        for res in search_response["results"]:
            raw = res.get("raw_content", res.get("content", ""))
            if not raw:
                continue

            # Strip HTML tags and collapse whitespace first
            cleaned = _clean_web_text(raw)
            if not re.search(r"\b(film|movie)\b", cleaned.lower()):
                continue

            # Extract structured fields before truncating
            duration_str = _extract_duration(cleaned)
            rating_str = _extract_rating(cleaned)

            # Extract genre hints from the full cleaned text
            genre_keywords = [
                "action",
                "adventure",
                "animation",
                "animated",
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
            ]
            cleaned_lower = cleaned.lower()
            detected_genres = [g for g in genre_keywords if g in cleaned_lower]
            genres_str = ", ".join(detected_genres) if detected_genres else ""

            # Strip reviewer attribution and boilerplate, then truncate to plot text
            plot_text = _extract_plot_text(cleaned)
            if not plot_text or plot_text == "N/A":
                continue

            # Match the exact context string structure used when DB embeddings were
            # created (csv_batch_to_documents.py) so the vector lands in the same space.
            context_string = (
                f"Item Id: unknown is a movie. "
                f"Its primary title is {movie_title}, "
                f"its original title is {movie_title}. "
                f"Its genres are {genres_str}. "
                f"Its duration is {duration_str} long, and has an average rating of {rating_str}. "
                f"Its plot summary is: '{plot_text}'. "
            )
            print(
                f"[Tavily] Built context string for '{movie_title}' "
                f"(genres={genres_str!r}, duration={duration_str!r}, rating={rating_str})."
            )
            return context_string

    except Exception as e:
        print(f"[Tavily] Fetch failed for '{movie_title}': {e}")
    return None


# ── Output formatter ───────────────────────────────────────────────────────────


def _format_results(rows: List[Any]) -> str:
    if not rows:
        return (
            "No high-quality movies matching your criteria were found in our directory."
        )

    formatted_output = "Here are your custom movie recommendations:\n"
    for i, row in enumerate(rows, 1):
        tconst, title, genres, rating, summary, duration, synopsis, distance = row
        score = round(1 - distance, 4) if distance is not None else "N/A"

        # Strip IMDB "Written by X" attribution that appears at the end of raw
        # plot_summary values scraped from IMDB (may be separated by whitespace or newline)
        summary_clean = (
            re.sub(
                r"\s*Written\s+by\s*[\w\s]*$", "", summary or "", flags=re.IGNORECASE
            ).strip()
            if summary
            else ""
        )

        clean_summary = (
            (summary_clean[:500] + "...")
            if summary_clean and len(summary_clean) > 500
            else (summary_clean or "No plot summary available.")
        )

        formatted_output += (
            f"\n🎬 {i}. {title} (Match Confidence: {score})\n"
            f"   - Genres: {genres} | Rating: {rating} | Duration: {duration}\n"
            f"   - Core Premise: {clean_summary}\n"
        )
    return formatted_output


# ── Recommender functions ──────────────────────────────────────────────────────
def recommend_similar_to_movie(
    movie_title: str, filter_genres: Optional[List[str]] = None
) -> str:
    """
    Recommends movies using vector similarity, leveraging the exact same subquery
    and scalar intersection multiplier model used in recommend_from_preferences.
    """
    conn = None
    try:
        config = load_config()
        conn = (
            psycopg2.connect(config)
            if isinstance(config, str)
            else psycopg2.connect(**config)
        )

        target_vector = None
        exclude_tconst = None
        seed_genres = []

        # 1. Look up target movie metrics from the DB
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT e.embedding, c.tconst,
                       string_to_array(LOWER(c.genres), ', '),
                       c.plot_summary
                FROM embeddings_table e
                JOIN cleaned_imdb c ON e.tconst = c.tconst
                WHERE c.primarytitle ILIKE %s AND e.chunk_id = 0
                LIMIT 1
                """,
                (movie_title,),
            )
            row = cursor.fetchone()
            if row:
                db_embedding, db_tconst, db_genres, db_plot = row
                exclude_tconst = db_tconst
                seed_genres = db_genres if db_genres else []
                if db_plot and db_plot.strip():
                    # Good embedding with plot — use it directly
                    target_vector = db_embedding
                else:
                    # In DB but plot_summary is missing — fetch via Tavily for a
                    # richer embedding that includes plot content in the vector
                    print(
                        f"[Recommender] '{movie_title}' in DB but plot missing — fetching via Tavily."
                    )
                    context_string = _fetch_context_string_via_tavily(movie_title)
                    if context_string:
                        vecs = query_to_vectors([context_string])
                        if vecs is not None and len(vecs) > 0 and vecs[0] is not None:
                            target_vector = vecs[0]
                    if target_vector is None:
                        target_vector = (
                            db_embedding  # fall back to existing plot-less embedding
                        )

        # 2. DB miss fallback (Tavily agent lookup)
        if target_vector is None:
            print(
                f"[Recommender] '{movie_title}' not in DB — fetching plot via Tavily."
            )
            context_string = _fetch_context_string_via_tavily(movie_title)
            if context_string:
                vectors = query_to_vectors([context_string])
                if vectors is not None and len(vectors) > 0 and vectors[0] is not None:
                    target_vector = vectors[0]

        if target_vector is None:
            return f"Error: Unable to generate a recommendation vector for '{movie_title}'."

        vector_str = (
            "[" + ",".join(map(str, target_vector)) + "]"
            if not isinstance(target_vector, str)
            else target_vector
        )

        # ── SYSTEMATIC PREFERENCE ALIGNMENT (SAME METHOD AS PREFERENCES) ──
        # Determine target fallback genres if the database row didn't exist
        target_genres = (
            seed_genres
            if seed_genres
            else [g.lower() for g in filter_genres] if filter_genres else []
        )

        all_params = []
        all_params.append(vector_str)  # Parameter for distance calculation

        # Build the exact same inner_select design pattern
        inner_select = """
            SELECT c.tconst, c.primarytitle, c.genres, c.averagerating,
                   c.plot_summary, c.duration, c.plot_synopsis,
                   (e.embedding <=> %s::vector) AS distance
        """

        if target_genres:
            genre_score_cases = " + ".join(
                [
                    f"(CASE WHEN c.genres ILIKE %s THEN 1 ELSE 0 END)"
                    for _ in target_genres
                ]
            )
            inner_select += (
                f", (1.0 + 0.4 * ({genre_score_cases})) AS intersection_multiplier"
            )
            all_params.extend([f"%{g}%" for g in target_genres])
        else:
            inner_select += ", 1.0 AS intersection_multiplier"

        # Build the matching inner_from_where constraints
        inner_from_where = """
            FROM embeddings_table e
            JOIN cleaned_imdb c ON e.tconst = c.tconst
            WHERE e.chunk_id = 0
              AND c.plot_summary IS NOT NULL
              AND c.plot_summary != ''
              AND c.averagerating >= 6.5
        """

        if exclude_tconst:
            inner_from_where += " AND c.tconst != %s"
            all_params.append(exclude_tconst)

        # NOT ILIKE with wildcard handles apostrophe/encoding variants
        inner_from_where += " AND c.primarytitle NOT ILIKE %s"
        all_params.append(f"%{movie_title}%")

        # Hard genre overlap: require results to share at least one genre with the
        # seed movie. Prevents semantic bleeding where physics vocabulary in
        # Oppenheimer matches sci-fi films that share no actual genre DNA.
        if target_genres:
            genre_overlap_clauses = " OR ".join(
                ["c.genres ILIKE %s" for _ in target_genres]
            )
            inner_from_where += f" AND ({genre_overlap_clauses})"
            all_params.extend([f"%{g}%" for g in target_genres])

        # Mirroring the preference routine's exact derived subquery table wrapping logic
        full_query = f"""
            SELECT tconst, primarytitle, genres, averagerating, 
                   plot_summary, duration, plot_synopsis, distance
            FROM (
                {inner_select}
                {inner_from_where}
            ) AS derived_recommendations
        """

        if target_genres:
            full_query += " ORDER BY (distance / intersection_multiplier) ASC LIMIT 5"
        else:
            full_query += " ORDER BY distance ASC LIMIT 5"

        # Execute query with cleanly built parameter pipeline
        with conn.cursor() as cursor:
            cursor.execute(full_query, tuple(all_params))
            movie_recs = cursor.fetchall()

        conn.close()
        return _format_results(movie_recs)

    except Exception as e:
        return f"Error executing movie recommendation: {e}"


def recommend_from_preferences(user_id: int) -> str:
    """
    Recommends movies by compiling existing vector snapshots of preferred titles,
    enforcing user favorite genres using an intersection sorting model to surface
    cross-genre overlaps first, and dropping low-quality blank records.
    """
    try:
        config = load_config()
        conn = (
            psycopg2.connect(config)
            if isinstance(config, str)
            else psycopg2.connect(**config)
        )

        user = func.get_user(current_user_id=user_id)
        if not user:
            return "Notice: No preference profile found. Please update your profile parameters first."
        prefs = user.preferences

        if not prefs.movie_interests_titles and not prefs.liked_genres:
            return "Your saved preferences profile is currently blank. Mention some movies or genres you enjoy so I can customize recommendations!"

        vectors_list = []
        exclude_tconsts = []

        # 1. Fetch real vectors for preferred titles
        if prefs.movie_interests_titles:
            with conn.cursor() as cursor:
                for title in prefs.movie_interests_titles:
                    cursor.execute(
                        """
                        SELECT e.embedding, c.tconst, c.plot_summary
                        FROM embeddings_table e
                        JOIN cleaned_imdb c ON e.tconst = c.tconst
                        WHERE LOWER(c.primarytitle) = LOWER(%s)
                          AND e.chunk_id = 0
                        LIMIT 1
                        """,
                        (title,),
                    )
                    row = cursor.fetchone()
                    if row:
                        db_emb, db_tconst, db_plot = row
                        exclude_tconsts.append(db_tconst)
                        if db_plot and db_plot.strip():
                            # Good embedding with plot — use it directly
                            emb = (
                                json.loads(db_emb)
                                if isinstance(db_emb, str)
                                else db_emb
                            )
                            vectors_list.append(np.array(emb))
                        else:
                            # In DB but plot_summary is missing — fetch via Tavily
                            # for a richer embedding that includes plot content
                            print(
                                f"[Recommender] '{title}' in DB but plot missing — fetching via Tavily."
                            )
                            context_string = _fetch_context_string_via_tavily(title)
                            if context_string:
                                vecs = query_to_vectors([context_string])
                                if (
                                    vecs is not None
                                    and len(vecs) > 0
                                    and vecs[0] is not None
                                ):
                                    vectors_list.append(np.array(vecs[0]))
                            else:
                                # Fall back to existing plot-less embedding rather than dropping it
                                emb = (
                                    json.loads(db_emb)
                                    if isinstance(db_emb, str)
                                    else db_emb
                                )
                                vectors_list.append(np.array(emb))
                    else:
                        print(
                            f"[Recommender] '{title}' not in DB — fetching plot via Tavily."
                        )
                        context_string = _fetch_context_string_via_tavily(title)
                        if context_string:
                            vecs = query_to_vectors([context_string])
                            if (
                                vecs is not None
                                and len(vecs) > 0
                                and vecs[0] is not None
                            ):
                                vectors_list.append(np.array(vecs[0]))

        # 2. Synthesize profile target vector
        if vectors_list:
            target_vector = np.mean(vectors_list, axis=0).tolist()
        else:
            return "Error: Could not retrieve plot data for any of your saved movie preferences."

        vector_str = "[" + ",".join(map(str, target_vector)) + "]"

        # ── SYSTEMATIC ORDERING OF PARAMETERS ──
        all_params = []

        # 1. Inner query SELECT projection parameters
        all_params.append(vector_str)  # Maps to the inner select distance vector

        inner_select = """
            SELECT c.tconst, c.primarytitle, c.genres, c.averagerating,
                   c.plot_summary, c.duration, c.plot_synopsis,
                   (e.embedding <=> %s::vector) AS distance
        """

        if prefs.liked_genres:
            genre_score_cases = " + ".join(
                [
                    f"(CASE WHEN c.genres ILIKE %s THEN 1 ELSE 0 END)"
                    for _ in prefs.liked_genres
                ]
            )
            inner_select += (
                f", (1.0 + 1.5 * ({genre_score_cases})) AS intersection_multiplier"
            )
            all_params.extend([f"%{g}%" for g in prefs.liked_genres])
        else:
            inner_select += ", 1.0 AS intersection_multiplier"

        # 2. Inner query WHERE criteria parameters
        inner_from_where = """
            FROM embeddings_table e
            JOIN cleaned_imdb c ON e.tconst = c.tconst
            WHERE e.chunk_id = 0
              AND c.plot_summary IS NOT NULL
              AND c.plot_summary != ''
        """

        if exclude_tconsts:
            inner_from_where += (
                f" AND c.tconst NOT IN ({','.join(['%s'] * len(exclude_tconsts))})"
            )
            all_params.extend(exclude_tconsts)

        # Exclude by ILIKE on each seed title to catch partial matches
        # (e.g. "Lara Croft: Tomb Raider" when seed title is "tomb raider")
        if prefs.movie_interests_titles:
            title_exclusions = " AND ".join(
                ["c.primarytitle NOT ILIKE %s" for _ in prefs.movie_interests_titles]
            )
            inner_from_where += f" AND ({title_exclusions})"
            all_params.extend([f"%{t}%" for t in prefs.movie_interests_titles])

        # NOTE: liked_genres is NOT added as a hard WHERE filter — it boosts via
        # intersection_multiplier in ORDER BY instead. A hard filter would exclude
        # all results when the mean vector (from e.g. Tomb Raider + Obsession) points
        # into a different genre space than liked_genres.

        # ── THE DECISIVE FIX: WRAP INTO A SUBQUERY Derived Table ──
        # Wrapping ensures that 'distance' and 'intersection_multiplier' are fully calculated
        # down to primitive scalar values before the sorting pipeline runs them.
        full_query = f"""
            SELECT tconst, primarytitle, genres, averagerating, 
                   plot_summary, duration, plot_synopsis, distance
            FROM (
                {inner_select}
                {inner_from_where}
            ) AS derived_recommendations
        """

        if prefs.liked_genres:
            full_query += " ORDER BY (distance / intersection_multiplier) ASC LIMIT 5"
        else:
            full_query += " ORDER BY distance ASC LIMIT 5"

        with conn.cursor() as cursor:
            cursor.execute(full_query, tuple(all_params))
            movie_recs = cursor.fetchall()

        conn.close()
        return _format_results(movie_recs)

    except Exception as e:
        return f"Error executing context preference engine loop: {e}"


# ── Test ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("\n=== Case 1: Recommend movies like the movie 'la la land' ===")
    print(recommend_similar_to_movie("la la land"))

    print("\n=== Case 2: Recommend movies based on my current preferences ===")
    print(recommend_from_preferences(79))
