import re
import time
import logging
import numpy as np
import psycopg2
from typing import Optional, Any, List

import os
import warnings

# 1. Suppress the unauthenticated HF Hub UserWarning
warnings.filterwarnings("ignore", message=".*unauthenticated requests to the HF Hub.*")

# 2. Disable the Hugging Face tqdm loading progress bars (the 100%|█████████| bar)
os.environ["HF_HUB_DISABLE_SYSPROGRESS_TRACKING"] = "1"

# (Optional) Ensure Hugging Face's internal logger is dead silent
os.environ["HF_HUB_DISABLE_VERBOSE_LOGGING"] = "1"

if not logging.getLogger().handlers:
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
    )
logging.getLogger("sentence_transformers").setLevel(logging.WARNING)
logging.getLogger("transformers").setLevel(logging.ERROR)
logging.getLogger("filelock").setLevel(logging.ERROR)
logging.getLogger("huggingface_hub").setLevel(logging.ERROR)
logging.getLogger("httpx").setLevel(logging.WARNING)

from movieRec.config import load_config
from movieRec.movieRecommendation2.sharedLibraries.user_query_to_vector import (
    query_to_vectors,
)
from movieRec.movieRecommendation2.entities.user2 import UserFunctions

func = UserFunctions()

# ── Shared helpers ─────────────────────────────────────────────────────────────


def _text_to_embedding(text: str) -> list:
    """Converts a plain text string into a vector embedding."""
    bge_query = f"Represent this sentence for searching relevant passages: {text}"
    embeddings = query_to_vectors([bge_query])
    result = embeddings[0]
    return result.tolist() if hasattr(result, "tolist") else result


def _get_movie_embedding(cursor, movie_title: str) -> Optional[list]:
    """
    Fetches embeddings for the single best-matching movie title (by tconst),
    checking both primarytitle and originaltitle, then averages all its chunks.
    """
    # Step 1: find the single best-matching tconst
    cursor.execute(
        """
        SELECT tconst
        FROM cleaned_imdb
        WHERE similarity(primarytitle, %s) > 0.5 OR similarity(originaltitle, %s) > 0.5
        ORDER BY GREATEST(similarity(primarytitle, %s), similarity(originaltitle, %s)) DESC
        LIMIT 1;
        """,
        (movie_title, movie_title, movie_title, movie_title),
    )
    row = cursor.fetchone()
    if not row:
        return None
    best_tconst = row[0]

    # Step 2: fetch ALL embedding chunks for that exact tconst only
    cursor.execute(
        """
        SELECT embedding
        FROM embeddings_table
        WHERE tconst = %s
        ORDER BY chunk_id ASC;
        """,
        (best_tconst,),
    )
    rows = cursor.fetchall()
    if not rows:
        return None

    embeddings = []
    for r in rows:
        emb = r[0]
        if isinstance(emb, str):
            emb = [float(x) for x in emb.strip("[]").split(",")]
        elif hasattr(emb, "tolist"):
            emb = emb.tolist()
        embeddings.append(emb)

    return np.mean(np.array(embeddings, dtype=float), axis=0).tolist()


def _parse_duration_to_minutes(duration_str: str) -> Optional[int]:
    """Parses user-supplied duration string into total minutes."""
    if not duration_str:
        return None
    duration_str = duration_str.lower().strip()

    decimal_hr = re.search(r"(\d+\.?\d*)\s*h", duration_str)
    if decimal_hr:
        hours = float(decimal_hr.group(1))
    else:
        hours = 0.0

    mins = re.search(r"(\d+)\s*min", duration_str)
    minutes = int(mins.group(1)) if mins else 0

    total = int(hours * 60) + minutes
    return total if total > 0 else None


def _format_results(rows: list) -> str:
    """Formats query rows into a clean readable string with full plot details."""
    if not rows:
        return "No recommendations found matching your criteria."

    result = ""
    for idx, row in enumerate(rows, 1):
        title, genres, rating, summary, duration, distance = row
        similarity_score = 1.0 / (1.0 + distance) if distance is not None else 0.0

        full_summary = summary or "No description available."

        result += (
            f"\nRecommendation #{idx}: '{title}' | Score: {similarity_score:.4f}\n"
            f"- Genres: {genres} | Rating: {rating} | Duration: {duration}\n"
            f"- Full Context for Agent to Summarize: {full_summary}\n"
        )
    return result.strip()


# ── Case 1 — "Recommend movies like 'La La Land'" ─────────────────────────────
def recommend_similar_to_movie(
    movie_title: str,
    filter_genres: Optional[List[str]] = None,
    duration: Optional[str] = None,
) -> str:
    print(
        f"--- Tool: recommend_similar_to_movie called with movie_title: '{movie_title}' ---"
    )
    start_time = time.perf_counter()
    config = load_config()

    with psycopg2.connect(**config) as conn:
        with conn.cursor() as cursor:

            # 1. Fetch seed movie embedding (pinned to best-matching tconst)
            seed_embedding = _get_movie_embedding(cursor, movie_title)
            if seed_embedding is None:
                return f"Could not find '{movie_title}' in the local database. Try a different title."

            # 2. Get seed tconst(s) to exclude from results
            cursor.execute(
                """
                SELECT tconst FROM cleaned_imdb
                WHERE similarity(primarytitle, %s) > 0.5 OR similarity(originaltitle, %s) > 0.5
                ORDER BY GREATEST(similarity(primarytitle, %s), similarity(originaltitle, %s)) DESC
                LIMIT 1;
                """,
                (movie_title, movie_title, movie_title, movie_title),
            )
            row = cursor.fetchone()
            seed_tconsts = [row[0]] if row else []

            # 3. Parse and construct filters dynamically
            blended = seed_embedding
            max_minutes = _parse_duration_to_minutes(duration) if duration else None

            params = [blended]

            genre_clause = ""
            if filter_genres:
                genre_conditions = " AND ".join(
                    ["c.genres ILIKE %s"] * len(filter_genres)
                )
                genre_clause = f"AND ({genre_conditions})"
                params += [f"%{g}%" for g in filter_genres]

            exclude_clause = ""
            if seed_tconsts:
                tconst_placeholders = ",".join(["%s"] * len(seed_tconsts))
                exclude_clause = f"AND e.tconst NOT IN ({tconst_placeholders})"
                params += seed_tconsts

            duration_clause = ""
            if max_minutes:
                duration_clause = """
                    AND (
                        COALESCE((REGEXP_MATCH(c.duration, '(\\d+)h'))[1]::int * 60, 0)
                        + COALESCE((REGEXP_MATCH(c.duration, '(\\d+)min'))[1]::int, 0)
                    ) BETWEEN 1 AND %s
                """
                params.append(max_minutes + 30)

            # Append final ordering embedding placeholder
            params.append(blended)

            # 4. Single consolidated query execution (Updated DISTINCT ON to use stable tconst)
            query = f"""
                WITH raw_matches AS (
                    SELECT DISTINCT ON (c.tconst)
                        c.primarytitle, c.genres, c.averagerating,
                        COALESCE(c.plot_summary, c.plot_synopsis, 'No description available.') AS plot_summary,
                        c.duration,
                        e.embedding <=> %s::vector AS distance
                    FROM embeddings_table e
                    JOIN cleaned_imdb c ON e.tconst = c.tconst
                    WHERE 1=1
                      {genre_clause}
                      {exclude_clause}
                      AND c.plot_summary IS NOT NULL
                      AND c.averagerating != 6.941349
                      {duration_clause}
                    ORDER BY c.tconst, e.embedding <=> %s::vector ASC
                )
                SELECT * FROM raw_matches
                ORDER BY distance ASC
                LIMIT 5;
            """

            cursor.execute(query, tuple(params))
            rows = cursor.fetchall()

    logging.getLogger(__name__).info(
        "`recommend_similar_to_movie` executed in %.3f ms",
        (time.perf_counter() - start_time) * 1000,
    )
    return _format_results(rows)


# ── Case 2 — "Recommend movies based on my current preferences" ───────────────


def recommend_from_preferences(user_id: Optional[Any] = None) -> str:
    print(f"--- Tool: recommend_from_preferences called with user_id: {user_id} ---")
    start_time = time.perf_counter()

    # 1. Validate and parse user_id
    if user_id is not None:
        try:
            user_id = int(str(user_id).strip())
        except ValueError:
            user_id = None

    if user_id is None or user_id == 0:
        return "Error: User ID is required. Please log in first."

    # 2. Fetch user preferences from DB
    user = func.get_user(current_user_id=user_id)
    if user is None:
        return f"Error: No user found with ID {user_id}."

    prefs = user.preferences
    liked_genres: List[str] = prefs.liked_genres or []
    interest_titles: List[str] = prefs.movie_interests_titles or []

    if not liked_genres and not interest_titles:
        return "You have no saved preferences. Add some genres or movie interests to your profile first."

    # 3. Build genre text embedding as preference signal
    pref_text = f"genres: {', '.join(liked_genres)}" if liked_genres else ""
    pref_embedding = _text_to_embedding(pref_text) if pref_text else None

    # 4. Fetch embeddings of each saved interest title — FIXED to look up both title columns
    config = load_config()
    movie_interest_embeddings = []
    exclude_tconsts: List[str] = []

    with psycopg2.connect(**config) as conn:
        with conn.cursor() as cursor:
            for title in interest_titles:
                # FIXED: Pinned lookup to check both original and primary titles
                cursor.execute(
                    """
                    SELECT tconst FROM cleaned_imdb
                    WHERE similarity(primarytitle, %s) > 0.5 OR similarity(originaltitle, %s) > 0.5
                    ORDER BY GREATEST(similarity(primarytitle, %s), similarity(originaltitle, %s)) DESC
                    LIMIT 1;
                    """,
                    (title, title, title, title),
                )
                row = cursor.fetchone()
                if not row:
                    continue
                best_tconst = row[0]
                exclude_tconsts.append(best_tconst)

                # Fetch ALL chunks for that exact tconst and average
                cursor.execute(
                    """
                    SELECT embedding FROM embeddings_table
                    WHERE tconst = %s
                    ORDER BY chunk_id ASC;
                    """,
                    (best_tconst,),
                )
                chunk_rows = cursor.fetchall()
                if not chunk_rows:
                    continue

                chunk_embeddings = []
                for r in chunk_rows:
                    emb = r[0]
                    if isinstance(emb, str):
                        emb = [float(x) for x in emb.strip("[]").split(",")]
                    elif hasattr(emb, "tolist"):
                        emb = emb.tolist()
                    chunk_embeddings.append(emb)

                avg_emb = np.mean(np.array(chunk_embeddings, dtype=float), axis=0)
                movie_interest_embeddings.append(avg_emb)

    # 5. Build final query embedding
    if movie_interest_embeddings and pref_embedding:
        avg_interest_emb = np.mean(movie_interest_embeddings, axis=0)
        final_embedding = (
            0.6 * np.array(avg_interest_emb, dtype=float)
            + 0.4 * np.array(pref_embedding, dtype=float)
        ).tolist()
    elif movie_interest_embeddings:
        final_embedding = np.mean(movie_interest_embeddings, axis=0).tolist()
    elif pref_embedding:
        final_embedding = pref_embedding
    else:
        return "Could not build a preference embedding. Try adding more interests."

    # 6. Vector search filtered by liked_genres, excluding saved interest tconsts
    with psycopg2.connect(**config) as conn:
        with conn.cursor() as cursor:
            tconst_placeholders = (
                ",".join(["%s"] * len(exclude_tconsts)) if exclude_tconsts else "NULL"
            )
            exclude_clause = (
                f"AND e.tconst NOT IN ({tconst_placeholders})"
                if exclude_tconsts
                else ""
            )

            if liked_genres:
                genre_conditions = " OR ".join(
                    ["c.genres ILIKE %s"] * len(liked_genres)
                )
                cursor.execute(
                    f"""
                    WITH raw_matches AS (
                        SELECT DISTINCT ON (c.tconst)
                               c.primarytitle, c.genres, c.averagerating,
                               COALESCE(c.plot_summary, c.plot_synopsis, 'No description available.') AS plot_summary,
                               c.duration,
                               e.embedding <=> %s::vector AS distance
                        FROM embeddings_table e
                        JOIN cleaned_imdb c ON e.tconst = c.tconst
                        WHERE ({genre_conditions})
                          {exclude_clause}
                          AND c.plot_summary IS NOT NULL
                          AND c.averagerating != 6.941349
                        ORDER BY c.tconst, e.embedding <=> %s::vector ASC
                    )
                    SELECT * FROM raw_matches
                    ORDER BY distance ASC
                    LIMIT 5;
                    """,
                    (
                        final_embedding,
                        *[f"%{g}%" for g in liked_genres],
                        *exclude_tconsts,
                        final_embedding,
                    ),
                )
            else:
                cursor.execute(
                    f"""
                    WITH raw_matches AS (
                        SELECT DISTINCT ON (c.tconst)
                               c.primarytitle, c.genres, c.averagerating,
                               COALESCE(c.plot_summary, c.plot_synopsis, 'No description available.') AS plot_summary,
                               c.duration,
                               e.embedding <=> %s::vector AS distance
                        FROM embeddings_table e
                        JOIN cleaned_imdb c ON e.tconst = c.tconst
                        WHERE 1=1
                          {exclude_clause}
                          AND c.plot_summary IS NOT NULL
                          AND c.averagerating != 6.941349
                        ORDER BY c.tconst, e.embedding <=> %s::vector ASC
                    )
                    SELECT * FROM raw_matches
                    ORDER BY distance ASC
                    LIMIT 5;
                    """,
                    (final_embedding, *exclude_tconsts, final_embedding),
                )
            movie_recs = cursor.fetchall()

    logging.getLogger(__name__).info(
        "`recommend_from_preferences` executed in %.3f ms",
        (time.perf_counter() - start_time) * 1000,
    )
    return _format_results(movie_recs)


# ── Test ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("\n=== Case 1: Recommend movies like the movie 'la la land' ===")
    print(recommend_similar_to_movie("la la land"))

    print(
        "\n=== Case 2: Recommend romance and comedy movies that are 1 hr long and have similar plot to the movie 'la la land' ==="
    )
    print(
        recommend_similar_to_movie(
            movie_title="la la land",
            filter_genres=["Romance", "Comedy"],
            duration="1 hr",
        )
    )

    print("\n=== Case 3: Recommend movies based on my current preferences ===")
    from movieRec.movieRecommendation2.tools_dir.pref_manager_dir.preference_manager import (
        update_preferences,
    )

    update_preferences(
        user_id=79,
        liked_genres=["Romance", "Sci-Fi"],
        movie_interests_titles=["Cinderella", "beauty and the beast"],
    )
    print(recommend_from_preferences(user_id=79))
