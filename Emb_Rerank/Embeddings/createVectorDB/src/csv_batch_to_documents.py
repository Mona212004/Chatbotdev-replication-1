#do not need to run
#function for processing rows of csv into batches before feeding into embedding model
import pandas as pd
from langchain_core.documents import Document
from Embeddings.createVectorDB.src.semantic_chunking import perform_semantic_chunking

def process_csv_batch_to_documents(df: pd.DataFrame)-> list[Document]:
    ''' Process a small batch of the DataFrame and returns a list of Document chunks.'''
    #create list to store all the chunks (List of Document objects)
    local_chunks: list[Document] = []
    for tconst, content in df.iterrows():
        # Fill missing values within the f-string for robustness
        original_title = "" if pd.isna(content['originaltitle']) else content['originaltitle']
        genres = "" if pd.isna(content['genres']) else content['genres']
        duration = "" if pd.isna(content['duration']) else content['duration']

        # Create Context Header string
        rating_str = f"{content['averageRating']:.1f}" if pd.notna(content['averageRating']) else 'N/A'
        context_header = (
            f"Item Id: {tconst} is a {content['titletype']}. "
            f"Its primary title is {content['primarytitle']}, "
            f"its original title is {original_title}. "
            f"Its genres are {genres}. "
            f"Its duration is {duration} long, and has an average rating of {rating_str}. "
        )

        # Create chunk with plot summary
        if pd.notna(content['plot_summary']):
            header_with_plot_summary = f"{context_header} Its plot summary is: '{content['plot_summary']}'. "
            #semantic chunking on plot_synopsis where continuity is important
            if pd.notna(content['plot_synopsis']) and len(content['plot_synopsis']) > 700:
                #print(f"-- Performing semantic chunking for plot_synopsis at tconst {tconst}. --")
                plot_synopsis_chunks = perform_semantic_chunking(tconst, content['plot_synopsis'], chunk_size=600, chunk_overlap=200)
                #A. append the plot summary chunk at chunk id 0
                #print(f"Storing plot summary chunk (ID 0) for {tconst}.")
                local_chunks.append(
                    Document(
                        page_content=header_with_plot_summary,
                        metadata={'tconst':tconst, 'chunk_id':0, 'chunk_type':'plot summary'}
                    )
                )
                # B. Append the synopsis Chunks (Chunk ID 1 onwards)
                for chunk_id, chunk in enumerate(plot_synopsis_chunks):
                    #concatenate content_header + plot_summary + each chunk
                    detailed_chunk_content = (
                        f"{header_with_plot_summary}"
                        f"Plot synopsis (part {chunk_id+1}): {chunk.page_content}"
                    )
                    metadata = chunk.metadata.copy(); metadata['chunk_id'] = chunk_id + 1
                    #print(f"Storing Synopsis Chunk (ID {chunk_id + 1}) for {tconst}.")
                    local_chunks.append(
                        Document(
                            page_content=detailed_chunk_content,
                            metadata=metadata
                        )
                    )
            else:
                #print(f"Plot_synopsis for tconst {tconst} is unavailable. Storing only Summary Chunk (ID 0).")
                local_chunks.append(
                    Document(
                        page_content=header_with_plot_summary,
                        metadata={'tconst':tconst, 'chunk_id':0, 'chunk_type':'plot summary'}
                    )
                ) 
        else:
            #print(f"Plot_summary for tconst {tconst} is unavailable. Storing only Context Header (ID 0).")
            local_chunks.append(
                Document(
                    page_content=context_header,
                    metadata={'tconst':tconst, 'chunk_id':0, 'chunk_type':'context_header'}
                )
            )
    return local_chunks