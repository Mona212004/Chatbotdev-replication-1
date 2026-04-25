#do not need to run
#insert a batch of embeddings (mulitple) into the table in imdb db
##Batch insert embeddings and metadata from dataframe into PostgreSQL database
import psycopg2
from pgvector.psycopg2 import register_vector
from  Embeddings.createVectorDB.src.config_conn import load_config
def insert_embeddings(embeddings_tuples):
    params = load_config()
    insert = "insert into embeddings_table(tconst, chunk_id, chunk_type, page_content, embedding) values(%s, %s, %s, %s, %s) ON CONFLICT (tconst, chunk_id) DO NOTHING"
    try:
        with psycopg2.connect(**params) as conn:
            with conn.cursor() as cur:
                register_vector(conn)
                cur.executemany(insert, embeddings_tuples)
            conn.commit()
    except (psycopg2.DatabaseError, Exception) as error:
        print(f"Error: {error}")
        conn.rollback()
        
