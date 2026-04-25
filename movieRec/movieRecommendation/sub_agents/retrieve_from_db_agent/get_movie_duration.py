# tools/get_movie_duration.py or similar
import psycopg2
from typing import Optional
from config import load_config

def get_movie_duration(tconst: Optional[str] = None, title: Optional[str] = None) -> Optional[str]:
    """
    Get the duration of a movie given either tconst ID or title (case-insensitive partial match).
    Returns duration as string (e.g., '142') or None if not found.
    """
    if not tconst and not title:
        return None

    config = load_config()
    try:
        with psycopg2.connect(**config) as conn:
            with conn.cursor() as cur:
                if tconst:
                    # Search by tconst (exact)
                    cur.execute(
                        "SELECT duration FROM cleaned_imdb WHERE tconst = %s",
                        (tconst,)
                    )
                else:
                    # Search by title (case-insensitive partial match)
                    search_term = f"%{title.lower()}%"
                    cur.execute(
                        """SELECT duration FROM cleaned_imdb 
                           WHERE LOWER(primarytitle) LIKE %s 
                              OR LOWER(originaltitle) LIKE %s
                           LIMIT 1""",
                        (search_term, search_term)
                    )

                row = cur.fetchone()
                if row and row[0] is not None:
                    return str(row[0])  # Ensure string return
                else:
                    print(f"No duration found for tconst={tconst}, title={title}")
                    return None

    except (psycopg2.DatabaseError, Exception) as error:
        print(f"Database error in get_movie_duration: {error}")
        return None