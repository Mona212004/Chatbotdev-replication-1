#use title to get plot summary
import psycopg2
from typing import Optional
from config import load_config

def get_movie_plot_summary(tconst: Optional[str] = None, title: Optional[str] = None) -> Optional[str]:
    """
    Get the plot summary of a movie given either tconst ID or title (case-insensitive partial match).
    Returns plot summary as string or None if not found.
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
                        "SELECT plot_summary FROM cleaned_imdb WHERE tconst = %s",
                        (tconst,)
                    )
                else:
                    # Search by title (case-insensitive partial match)
                    search_term = f"%{title.lower()}%"
                    cur.execute(
                        """SELECT plot_summary FROM cleaned_imdb 
                           WHERE LOWER(primarytitle) LIKE %s 
                              OR LOWER(originaltitle) LIKE %s
                           LIMIT 1""",
                        (search_term, search_term)
                    )

                row = cur.fetchone()
                if row and row[0] is not None:
                    summary = row[0].strip()  # Remove accidental leading/trailing whitespace
                    return summary if summary else None
                else:
                    print(f"No plot summary found for tconst={tconst}, title={title}")
                    return None

    except (psycopg2.DatabaseError, Exception) as error:
        print(f"Database error in get_movie_plot_summary: {error}")
        return None