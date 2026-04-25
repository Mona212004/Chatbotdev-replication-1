# tools/check_if_movie_exists_in_db.py
import psycopg2
from typing import Optional
from config import load_config

def check_if_movie_exists_in_db(title: str) -> bool:
    """
    Checks if a movie with partial matching title exists in the database (case-insensitive).
    Returns True if at least one match found, False otherwise.
    """
    if not title or not title.strip():
        return False

    search_term = f"%{title.strip().lower()}%"
    config = load_config()
    try:
        with psycopg2.connect(**config) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """SELECT 1 FROM cleaned_imdb 
                       WHERE LOWER(primarytitle) LIKE %s 
                          OR LOWER(originaltitle) LIKE %s
                       LIMIT 1""",
                    (search_term, search_term)
                )
                return cur.fetchone() is not None
    except (psycopg2.DatabaseError, Exception) as error:
        print(f"Database error in check_if_movie_exists_in_db: {error}")
        return False