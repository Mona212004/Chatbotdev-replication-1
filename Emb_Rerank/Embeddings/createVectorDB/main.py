#main for generating embeddings and inserting into vector db
#run main.py
import os
import sys
import warnings

current_dir = os.path.dirname(os.path.abspath(__file__)) #dir where main.py is located
project_root = os.path.abspath(os.path.join(current_dir, '..', '..')) #points to root dir 2 levels up = Emb_Rerank
if project_root not in sys.path:
    sys.path.insert(0, project_root) 

from Embeddings.createVectorDB.src.config_db import imdb_filepath, read_chunk_size
import pandas as pd
from Embeddings.createVectorDB.src.csv_batch_to_documents import process_csv_batch_to_documents
from Embeddings.createVectorDB.src.device import get_device
from Embeddings.createVectorDB.src.generate_embeddings import get_embeddings
from Embeddings.createVectorDB.src.config_db import model
from Embeddings.createVectorDB.src.listofDict_to_listofTuples import transform_embeddings_listofDict_to_listofTuples
from Embeddings.createVectorDB.src.insert_embeddings import insert_embeddings
import time
import logging

def main():
    start_time = time.time()  # Start measuring execution time
    
    # Set up logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler('main.log'),  # Log to file
            logging.StreamHandler()  # Also log to console
        ]
    )

    os.environ['TF_CPP_MIN_LOG_LEVEL'] = '3'  # Suppress TensorFlow logs
    warnings.filterwarnings('ignore')
    
    batch_count = 0
    batch_size = 0
    total_no_embedding_chunks = 0
    devices = get_device()
    #read_chunk_size
    for batch in pd.read_csv(imdb_filepath, chunksize=read_chunk_size, index_col=0, low_memory=False):
    #for batch in [pd.read_csv(imdb_filepath, nrows=5, index_col=0, low_memory=False)]: #for testing
        logging.info(f"--- Start reading batch #{batch_count} ---")
        try:
            #chunk each batch of csv rows before feeding into embedding model
            chunking_per_batch_preEmbedding = process_csv_batch_to_documents(batch)
            logging.info(f"--- Start chunking batch #{batch_count} ---")
            logging.info(f"--- Number of chunks in batch #{batch_count}: {len(chunking_per_batch_preEmbedding)}")
        except Exception as e:
            logging.error(f"Chunking batch #{batch_count} failed: {str(e)}")
            raise Exception(f"Chunking batch #{batch_count} failed.")
        
        try:
            #after chunking, feed into model
            logging.info(f"Feed batch #{batch_count}'s {len(chunking_per_batch_preEmbedding)} chunks into model")
            embeddings, num_chunks = get_embeddings(chunking_per_batch_preEmbedding, model, devices)
        except Exception as e:
            logging.error(f"Failed to feed batch #{batch_count}'s {len(chunking_per_batch_preEmbedding)} chunks into model: {str(e)}")
            raise Exception(f"Failed to feed batch #{batch_count}'s {len(chunking_per_batch_preEmbedding)} chunks into model")
        #print(f"Generated embeddings for chunk{batch_count}")
        
        try:
            #transform embeddings from list of dictionaries to list of tuples
            embeddings_tuples = transform_embeddings_listofDict_to_listofTuples(embeddings, num_chunks)
            #insert multiple rows of data into postgresql from the tuples
            insert_embeddings(embeddings_tuples)
            logging.info(f"Batch {batch_count} complete: {len(embeddings_tuples)} inserted.")
        except Exception as e:
            logging.error(f"Failed to insert batch #{batch_count}'s {len(chunking_per_batch_preEmbedding)} embeddings into db: {str(e)}")
            raise Exception(f"Failed to insert batch #{batch_count}'s {len(chunking_per_batch_preEmbedding)} embeddings into db.")

        logging.info("")
        batch_count +=1
        batch_size += len(batch)
        total_no_embedding_chunks += len(embeddings_tuples)
    logging.info(f"Total rows from all batches: {batch_size}") #726031
    logging.info(f"Total number of embedding chunks from all batches: {total_no_embedding_chunks}")

    end_time = time.time()  # End measuring execution time
    execution_time = end_time - start_time
    logging.info(f"Total execution time: {execution_time:.2f} seconds")

if __name__ == '__main__':
    main()