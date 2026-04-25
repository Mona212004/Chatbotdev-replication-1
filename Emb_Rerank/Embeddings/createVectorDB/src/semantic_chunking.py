#semantic chunking function for plot_synopsis
#do not need to run
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_core.documents import Document

def perform_semantic_chunking(tconst: str, document, chunk_size=600, chunk_overlap=200):
    """
    Performs semantic chunking on a using recursive character splitting 
    at logical text boundaries.
    
    Args:
        document (str): The text document to process (plot_synopsis)
        chunk_size (int): The target size of each chunk in characters
        chunk_overlap (int): The number of characters of overlap between chunks
        
    Returns:
        list: The semantically chunked documents with metadata
    """
    #print(f"--- Processing ID: {tconst} ---")
    # Create the text splitter with semantic separators
    text_splitter = RecursiveCharacterTextSplitter(
        separators=["\n\n", "\n", ". ", " ", ""],
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        length_function=len
    )
    
    # Split the text into semantic chunks
    semantic_chunks = text_splitter.split_text(document)
    #print(f"Document (plot_synopsis) split into {len(semantic_chunks)} semantic chunks.")
    
    # Convert to Document objects with enhanced metadata
    documents = []
    
    for i, chunk in enumerate(semantic_chunks):
        doc = Document(
            page_content=chunk,
            metadata={
                "tconst": tconst,
                "chunk_id": i+1,
                "total_chunks": len(semantic_chunks),
                "chunk_size": len(chunk),
                "chunk_type": "synopsis_detail"
            }
        )
        documents.append(doc)
    
    return documents