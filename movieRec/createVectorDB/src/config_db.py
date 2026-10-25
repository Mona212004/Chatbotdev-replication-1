# do not need to run
# data source to generate embeddings from
import os
base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))
imdb_filepath = os.path.join(base_dir, "ProcessedData", "cleaned_imdb_202510121521.csv")
# read_chunk_size
read_chunk_size = 50000

from sentence_transformers import SentenceTransformer, SimilarityFunction
model = SentenceTransformer('BAAI/bge-base-en-v1.5', similarity_fn_name=SimilarityFunction.DOT_PRODUCT)
