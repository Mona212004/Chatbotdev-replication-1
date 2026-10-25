def transform_embeddings_listofDict_to_listofTuples(embeddings, num_chunks):
    embeddings_tuples = []
    for i in range(num_chunks):
        each_chunk = embeddings[i]
        values_tuple = (each_chunk['tconst'],
                        each_chunk['chunk_id'],  # Or use i if it's the index
                        each_chunk['chunk_type'],
                        each_chunk['page_content'],
                        each_chunk['embedding'].tolist() if hasattr(each_chunk['embedding'], 'tolist') else each_chunk['embedding'])
        embeddings_tuples.append(values_tuple)
    return embeddings_tuples
#do not need to run