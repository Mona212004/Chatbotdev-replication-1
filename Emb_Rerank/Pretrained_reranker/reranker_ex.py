import sys, os
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_dir,'..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from Embeddings.UserQuery.query_embedding import query_to_vectors
from archive.vector_similarity_search_topN import vector_similarity_search_topN
import time
from Pretrained_reranker.load_reranker import load_reranker

def reranker_example():
    input = ["What are some films about romance with a lot of action and adventure?", "Find me documentary films about famous historical sporting events or fights."]
    user_query_embeddings = query_to_vectors(input)
    try:
        model = load_reranker()
    except Exception as e:
        print(f"Failed to load reranker model: {e}")
        return
    
    for i, query in enumerate(user_query_embeddings):
        top10_results = vector_similarity_search_topN(query,10)
        print(f"--- Results for Query: '{input[i]}' ---")
        # Extract the query (input[i]) and the descriptive string (result[3])
        # from the tuple returned by gettop10test.
        pairs = [[input[i],result[2]] for result in top10_results]
        scores = model.predict(pairs, batch_size=32)
        scored_results = list(zip(top10_results, scores))
        scored_results.sort(key=lambda x: x[1], reverse=True)
        top_10_results = scored_results[0:10]
        # Extract the highest-scoring single result for the summary printout
        top_result_tuple, top_score = top_10_results[0]
        # Get the descriptive string (still assuming index [2] is the string)
        original_result = top_result_tuple[2].strip() 
        print(f"\n TOP RERANKED RESULT (Score: {top_score:.4f}):")
        print(original_result)
        print("\n--- TOP 10 Reranked Results (Sorted Highest to Lowest Score) ---")
        for result_tuple, score in top_10_results: # Iterate only over the top 10
            # Print the title and score for comparison
            # Assuming title is result_tuple[1] and ID is result_tuple[0]
            print(f"Score: {score:.4f} | Titletype: {result_tuple[1]} | ID: {result_tuple[0]}")
            
if __name__ == "__main__":
    start_time = time.time()
    reranker_example()
    print("Execution time: --- %s seconds ---" % (time.time() - start_time))