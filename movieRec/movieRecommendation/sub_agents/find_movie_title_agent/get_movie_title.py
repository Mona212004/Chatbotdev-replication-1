#use genres, plot summary, plot synopsis with vector similarity search to get title
#if user mentions looking for a movie title, ask them for genres, plot synopsis, plot summary and topN results they want
#convert user query to vector embeddings
#vector similarity search 
#rerank
# tools/get_movie_title.py
import psycopg2
import numpy as np
from typing import List, Dict, Any
from config import load_config
from movieRecommendation.sharedLibraries.load_reranker import load_reranker

def get_movie_title(
    query_text: str,
    query_embedding: List[float] | np.ndarray,
    topN: int = 10,
    rerank: bool = True
) -> List[Dict[str, Any]]:
    """
    Find topN most relevant movies using vector similarity + optional cross-encoder reranking.
    Matches user queries involving title, genres, plot summary, or synopsis.
    Returns list of dicts with: title, genres, summary, synopsis, rerank_score (if reranked)
    """
    if not query_text.strip() or not query_embedding:
        return []

    # Convert embedding to list for pgvector
    if isinstance(query_embedding, np.ndarray):
        query_embedding = query_embedding.tolist()

    config = load_config()
    candidates = []
    try:
        with psycopg2.connect(**config) as conn:
            with conn.cursor() as cur:
                # Fetch more candidates for better reranking
                fetch_count = topN * 2 if rerank else topN
                cur.execute(
                    "SELECT * FROM get_movie_title(%s, %s)",
                    (query_embedding, fetch_count)
                )
                rows = cur.fetchall()
                print(f"Fetched {len(rows)} candidate movies from vector search")
                for row in rows:
                    title, genres, summary, synopsis = row
                    # Build comprehensive document text for reranker
                    parts = [f"Title: {title}"]
                    if genres:
                        parts.append(f"Genres: {genres}")
                    if summary:
                        parts.append(f"Summary: {summary}")
                    if synopsis:
                        parts.append(f"Synopsis: {synopsis}")

                    doc_text = ". ".join(parts)
                    candidates.append({
                        "title": title or "Unknown Title",
                        "genres": genres or "Genres N/A",
                        "summary": summary or "Summary N/A",
                        "synopsis": synopsis or "Synopsis N/A",
                        "doc_text": doc_text
                    })

        # Reranking step
        if rerank and candidates:
            try:
                reranker = load_reranker()
                pairs = [[query_text, cand["doc_text"]] for cand in candidates]
                scores = reranker.predict(pairs)

                for cand, score in zip(candidates, scores):
                    cand["rerank_score"] = float(score)
                candidates.sort(key=lambda x: x["rerank_score"], reverse=True)

                print(f"Reranked {len(candidates)} results")
                if candidates:
                    top = candidates[0]
                    print(f"TOP RERANKED: {top['title']} (Score: {top['rerank_score']:.4f})")
            except Exception as e:
                print(f"Reranker failed: {e}. Returning vector-ranked results.")

        return candidates[:topN]

    except Exception as error:
        print(f"Error in get_movie_title: {error}")
        return []
    
"""
create or replace function get_movie_title(query_embedding vector(768), topN integer)
 returns table(primarytitle character varying, genres character varying, plot_summary character varying, plot_synopsis character varying) as
$$
begin 
 return query
 select c.primarytitle, c.genres, c.plot_summary, c.plot_synopsis
 from embeddings_table t 
 join cleaned_imdb c on t.tconst = c.tconst
 order by t.embedding <=> query_embedding asc limit topN;
end; $$ language plpgsql;
"""
#cosine similarity <=>, lower num = higher similarity
#this function is only for vector sim search, it cannot do filtering search by genres or average rating