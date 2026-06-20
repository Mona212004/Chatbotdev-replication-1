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


def _fetch_context_string_via_tavily(movie_title: str) -> Optional[str]:
    """
    Fetches a movie's plot from IMDB via Tavily and formats it into the same
    context string structure used when the DB embeddings were created:

        "Its primary title is {title}. Its plot summary is: '{plot_text}'."

    This ensures the generated embedding lands in the same vector space as the DB.
    Returns None if the fetch fails or returns no usable content.
    """
    if not TAVILY_API_KEY:
        print("[Tavily] TAVILY_API_KEY not found in environment.")
        return None
    try:
        tavily_client = TavilyClient(api_key=TAVILY_API_KEY)

        # IMPROVEMENT 1: Anchor the query explicitly to avoid raw literal translations
        # appending "synopsis plot summary" directs the API to structured movie profiles.
        refined_query = f'"{movie_title}" movie synopsis plot summary site:imdb.com'

        search_response = tavily_client.search(
            query=refined_query,
            search_depth="advanced",
            max_results=2,
            include_raw_content=True,
        )
        if not search_response or "results" not in search_response:
            return None

        for res in search_response["results"]:
            url = res.get("url", "")
            if "imdb.com/list/" in url:
                continue  # Skip generic IMDB list pages, same as find_movie_tool.py
            raw = res.get("raw_content", res.get("content", ""))
            if not raw:
                continue

            # Clean HTML, then take enough text to cover plot summary + early synopsis.
            plot_text = _clean_web_text(raw)[:800]
            if not plot_text or plot_text == "N/A":
                continue

            # IMPROVEMENT 2: Establish a structural context anchor in the string itself.
            # If a title is highly abstract, adding a neutral cinematic identifier ("feature film narrative")
            # grounds the vector embedding back into standard storytelling frameworks instead of letting
            # the embedding engine interpret the title as a raw literal disaster scenario.
            context_string = (
                f"Item Id: unknown is a movie. "
                f"Its primary title is {movie_title}, "
                f"its original title is {movie_title}. "
                f"This feature film narrative details the following events. "
                f"Its plot summary is: '{plot_text}'. "
            )
            print(
                f"[Tavily] Built context string for '{movie_title}' ({len(context_string)} chars)."
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

        # Safe tracking boundary for truncated output previews
        clean_summary = (
            (summary[:500] + "...")
            if summary and len(summary) > 500
            else (summary or "No plot summary available.")
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
                SELECT e.embedding, c.tconst, string_to_array(LOWER(c.genres), ', ')
                FROM embeddings_table e
                JOIN cleaned_imdb c ON e.tconst = c.tconst
                WHERE c.primarytitle ILIKE %s AND e.chunk_id = 0
                LIMIT 1
                """,
                (movie_title,),
            )
            row = cursor.fetchone()
            if row:
                target_vector = row[0]
                exclude_tconst = row[1]
                seed_genres = row[2] if row[2] else []

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
                f", (1.0 + 0.15 * ({genre_score_cases})) AS intersection_multiplier"
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
              AND c.averagerating >= 4.5
        """

        if exclude_tconst:
            inner_from_where += " AND c.tconst != %s"
            all_params.append(exclude_tconst)

        inner_from_where += " AND LOWER(c.primarytitle) != LOWER(%s)"
        all_params.append(movie_title)

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
                        SELECT e.embedding, c.tconst
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
                        emb = json.loads(row[0]) if isinstance(row[0], str) else row[0]
                        vectors_list.append(np.array(emb))
                        exclude_tconsts.append(row[1])
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
                f", (1.0 + 0.5 * ({genre_score_cases})) AS intersection_multiplier"
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

        if prefs.liked_genres:
            genre_queries = ["c.genres ILIKE %s" for _ in prefs.liked_genres]
            inner_from_where += f" AND ({' OR '.join(genre_queries)})"
            all_params.extend([f"%{g}%" for g in prefs.liked_genres])

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
