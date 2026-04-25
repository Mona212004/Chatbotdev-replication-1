#do not need to run
import psycopg2
from config_conn import load_config
from pgvector.psycopg2 import register_vector

def install_extensions():
    #install pgvector sql
    install1 = "CREATE EXTENSION IF NOT EXISTS vector;"
    #install pgvectorscale
    install2 = "CREATE EXTENSION IF NOT EXISTS vectorscale CASCADE;"

    params = load_config()
    try:
        with psycopg2.connect(**params) as conn:
            with conn.cursor() as cur:
                cur.execute(install1)
                cur.execute(install2)
                conn.commit() 
            # Register the vector type with psycopg2
            register_vector(conn)
            print(f"Successfully installed and registered vector type")
    except (psycopg2.DatabaseError, Exception) as error:
        print(error)
        
def create_table():
    params = load_config()
    create = """create table embeddings_table (
        id BIGINT PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
        tconst text,
        chunk_id integer,
        chunk_type text,
        page_content text,
        embedding vector(768)
        );"""
    try: 
        with psycopg2.connect(**params) as conn:
            with conn.cursor() as cur:
                register_vector(conn)
                cur.execute(create)
                # Add unique constraint safely (drop if exists, then add)
                cur.execute("ALTER TABLE embeddings_table DROP CONSTRAINT IF EXISTS unique_tconst_chunk;")
                cur.execute("ALTER TABLE embeddings_table ADD CONSTRAINT unique_tconst_chunk UNIQUE (tconst, chunk_id);")
                conn.commit()
            print(f"Table successfully created")
    except (psycopg2.DatabaseError, Exception) as error:
        print(error)
        
if __name__=="__main__":
    install_extensions()
    create_table()
    
#verify: psql -U postgres imdb, \dt, select * from embeddings_table;
# id | tconst | chunk_id | chunk_type | page_content | embedding 