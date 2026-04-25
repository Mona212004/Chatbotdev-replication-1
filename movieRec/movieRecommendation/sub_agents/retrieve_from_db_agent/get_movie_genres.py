# tools/get_movie_genres.py
import psycopg2
from typing import Optional
from config import load_config

def get_movie_genres(tconst: Optional[str] = None, title: Optional[str] = None) -> Optional[str]:
    """
    Get the genres of a movie given either tconst ID or title (case-insensitive partial match).
    Returns the raw comma-separated genre string exactly as stored in the database
    (e.g., "Action,Sci-Fi,Thriller" or "Romance"), or None if not found.
    """
    if not tconst and not title:
        return None

    config = load_config()
    try:
        with psycopg2.connect(**config) as conn:
            with conn.cursor() as cur:
                if tconst:
                    cur.execute(
                        "SELECT genres FROM cleaned_imdb WHERE tconst = %s",
                        (tconst,)
                    )
                else:
                    search_term = f"%{title.lower()}%"
                    cur.execute(
                        """SELECT genres FROM cleaned_imdb 
                           WHERE LOWER(primarytitle) LIKE %s 
                              OR LOWER(originaltitle) LIKE %s
                           ORDER BY startyear DESC NULLS LAST
                           LIMIT 1""",
                        (search_term, search_term)
                    )

                row = cur.fetchone()
                if row and row[0] is not None:
                    genres_str = row[0].strip()
                    return genres_str if genres_str else None
                else:
                    print(f"No genres found for tconst={tconst}, title={title}")
                    return None

    except (psycopg2.DatabaseError, Exception) as error:
        print(f"Database error in get_movie_genres: {error}")
        return None