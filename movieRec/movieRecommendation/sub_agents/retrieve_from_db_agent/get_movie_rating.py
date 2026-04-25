#use title to get rating
import psycopg2
from typing import Optional
from config import load_config

def get_movie_rating(tconst: Optional[str] = None, title: Optional[str] = None) -> Optional[float]:
    """
    Get the average rating of a movie given either tconst ID or title (case-insensitive partial match).
    Returns rating as float (e.g., 3.4) or None if not found.
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
                        "SELECT averagerating FROM cleaned_imdb WHERE tconst = %s",
                        (tconst,)
                    )
                else:
                    # Search by title (case-insensitive partial match)
                    search_term = f"%{title.lower()}%"
                    cur.execute(
                        """SELECT averagerating FROM cleaned_imdb 
                           WHERE LOWER(primarytitle) LIKE %s 
                              OR LOWER(originaltitle) LIKE %s
                           LIMIT 1""",
                        (search_term, search_term)
                    )

                row = cur.fetchone()
                if row and row[0] is not None:
                    return float(row[0])  # Ensure float return
                else:
                    print(f"No rating found for tconst={tconst}, title={title}")
                    return None

    except (psycopg2.DatabaseError, Exception) as error:
        print(f"Database error in get_movie_rating: {error}")
        return None