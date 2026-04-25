from sentence_transformers import CrossEncoder
import os
import subprocess
import time

def load_reranker():
    try:
        model = CrossEncoder("BAAI/bge-reranker-large", 
                             max_length=512, device='cuda')
        if model:
            print("Reranker model loaded successfully.")
            return model
    except Exception as e:
        print("Failed to load the reranker model.")
        print(f"An error occurred while loading the optimized reranker: {e}")
        return
    
#if __name__ == "__main__":
#    start_time = time.time()
#    reranker_model = load_reranker()
#    end_time = time.time()
#    print(f"Total time taken: {end_time - start_time} seconds")
