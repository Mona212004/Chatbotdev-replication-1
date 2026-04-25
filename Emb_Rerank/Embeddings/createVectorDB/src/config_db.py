#do not need to run
#data source to generate embeddings from
imdb_filepath = r'C:\Users\M\Documents\chatbotdev\ProcessedData\cleaned_imdb_202510121521.csv'
#read_chunk_size
read_chunk_size = 50000

from sentence_transformers import SentenceTransformer, SimilarityFunction
model = SentenceTransformer('BAAI/bge-base-en-v1.5', similarity_fn_name=SimilarityFunction.DOT_PRODUCT)

