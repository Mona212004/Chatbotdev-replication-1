import os
import time
import logging
import re
from typing import Any, Optional, List
import psycopg2

# Ensure basic logging configuration if none exists
if not logging.getLogger().handlers:
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
    )
from movieRec.config import load_config

def get_movie_info(movie_title : str) -> str:
    """
    Gets movie information from the local database given a movie title.
    """
    print(f"--- Tool: get_movie_info tool called with movie_title: {movie_title} ---")
    start_time = time.perf_counter()

    # 1. Execute Local Vector Database Retrieval
    rows = []
    config = load_config()
    try:
        with psycopg2.connect(**config) as conn:
            with conn.cursor() as cursor:
                query = """
                    SELECT primarytitle, genres, averagerating, plot_summary, duration, plot_synopsis
                    FROM cleaned_imdb
                    WHERE primarytitle = %s
                """
                cursor.execute(query, (movie_title,))
                rows = cursor.fetchall()
    except Exception as db_err:
        logging.getLogger(__name__).error(f"Database transaction failure: {db_err}")

    # 2. Compile Standardized System Report Structure
    if rows:
        local_candidates_block = ""
        for idx, row in enumerate(rows, 1):
            title, genres, rating, summary, duration, synopsis = row

            clean_summary = (
                (summary[:250] + "...") if summary and len(summary) > 250 else summary
            )
            clean_synopsis = (
                (synopsis[:400] + "...")
                if synopsis and len(synopsis) > 400
                else (synopsis or "N/A")
            )

            local_candidates_block += (
                f"\nCandidate #{idx}: '{title}'\n"
                f"- Genres: {genres} | Rating: {rating} | Duration: {duration}\n"
                f"- Plot Summary: {clean_summary}\n"
                f"- Plot Synopsis: {clean_synopsis}\n"
            )
    else:
        print("--- Movie not found in local database ---")
        local_candidates_block = f"\n⚠️ NOTICE: Local database query yielded 0 results for movie title '{movie_title}'."

    logging.getLogger(__name__).info(
        "`find_movie_title` executed successfully in %.3f ms",
        (time.perf_counter() - start_time) * 1000,
    )
    return local_candidates_block

if __name__ == "__main__":
    # Example usage for testing
    test_title = "The Addams Family"
    info = get_movie_info(test_title)
    print(info)