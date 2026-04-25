#run this after running main.py
#index the embedding table database after generating embeddings
#index the embeddings: pgvectorscale offers a more cost-efficient and powerful index type for pgvector data: StreamingDiskANN
# Create an index on the data for faster retrieval

from config_conn import load_config
import psycopg2
from pgvector.psycopg2 import register_vector
from alive_progress import alive_bar
import time
import logging

#set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def index_embeddings_table():
    params = load_config()
    create_index = "create index embedding_idx on embeddings_table using diskann (embedding vector_cosine_ops);"
    #start timer
    start_time = time.time()
    logging.info("Starting the indexing process.")

    try:
        with psycopg2.connect(**params) as conn:
            register_vector(conn)
            logging.info("Successfully connected to the database.")
            with conn.cursor() as cur:
                logging.warning("Attempting to drop existing index 'embedding_idx' if it exists.")
                cur.execute("DROP INDEX IF EXISTS embedding_idx;")
                
                # Simple spinner with elapsed time
                with alive_bar(
                    title='Indexing embeddings',
                    bar='halloween',
                    unknown='waves',  # Shows waves moving through the bar
                    elapsed=True,
                    stats=False,
                    monitor=False
                ) as bar:
                    cur.execute(create_index)
                    bar() # Manually trigger the end state of the bar/spinner
                logging.info(f"Index creation query finished. Status: {cur.statusmessage}")
            
            conn.commit()
            #stop timer
            end_time = time.time()
            elapsed_time = end_time - start_time
            logging.info(f"Index created using diskann on embeddings_table.embedding successfully.")
            logging.info(f"Total execution time for indexing: {elapsed_time:.2f} seconds.")
            print(f"Index created using diskann on embeddings_table.embedding")
            print(f"Total execution time: {elapsed_time:.2f} seconds.")
    except (psycopg2.DatabaseError, Exception) as error:
        logging.error(f"An error occurred during indexing: {error}")
        print(error)
        
if __name__=="__main__":
    index_embeddings_table()

#after running, check the size of embeddings in each row => 768
# verify the indexing #index scan worked instead of seq scan