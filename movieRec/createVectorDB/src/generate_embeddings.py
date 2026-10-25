#do not need to run
def get_embeddings(chunked_batch, model, devices):
    passages = [doc.page_content for doc in chunked_batch]
    # Start multi-process pool (one-time setup for parallel encoding across devices)
    pool = model.start_multi_process_pool(devices)
    # Encode with multi-process (distributes across GPUs/processes)
    p_embeddings = model.encode_multi_process(
        passages,
        pool=pool,
        batch_size=64,  # Per-process batch size; tune for VRAM (higher = faster)
        chunk_size=512,  # Size of input chunks sent to each process; tune for balance
        show_progress_bar=True  # Optional progress tracking
    )
    
    # Stop the pool (cleanup; do this after all batches if reusing across calls)
    model.stop_multi_process_pool(pool)
    #records to store, in list of dictionaries
    records_to_insert = []
    for doc, p_embedding in zip(chunked_batch, p_embeddings):
        record = {
            'tconst' : doc.metadata['tconst'],
            'chunk_id' : doc.metadata['chunk_id'],
            'chunk_type' : doc.metadata['chunk_type'],
            'page_content' : doc.page_content,
            'embedding' : p_embedding.tolist() # Convert tensor to list for storage
        }
        records_to_insert.append(record)
    return records_to_insert, len(passages)