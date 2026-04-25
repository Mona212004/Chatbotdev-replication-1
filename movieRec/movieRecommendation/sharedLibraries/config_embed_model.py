from sentence_transformers import SentenceTransformer, SimilarityFunction
model = SentenceTransformer('BAAI/bge-base-en-v1.5', similarity_fn_name=SimilarityFunction.DOT_PRODUCT)

