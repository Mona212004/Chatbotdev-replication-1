#only run once to create user table
import psycopg2
from Emb_Rerank.Embeddings.createVectorDB.src.config_conn import load_config

def create_user_table():
    """Create users table in the PostgreSQL database with the same connection as the embedding table."""
    command = """
        create table user_data (
            user_id SERIAL PRIMARY KEY,
            user_name text NOT NULL,
            preferences JSONB NOT NULL
        )
        """
    try:
        conn = load_config()
        with psycopg2.connect(**conn) as connection:
            with connection.cursor() as cur:
                cur.execute(command)
    except (psycopg2.DatabaseError, Exception) as error:
        print(f"An error occurred: {error}")
        
if __name__ == '__main__':
    create_user_table()