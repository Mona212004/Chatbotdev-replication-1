import os
import time
import logging
import re
from typing import Any, Optional, List
import psycopg2

# Ensure basic logging configuration if none exists
if not logging.getLogger().handlers:
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
    )
logging.getLogger("sentence_transformers").setLevel(logging.WARNING)
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("huggingface_hub").setLevel(logging.ERROR)
logging.getLogger("urllib3").setLevel(logging.WARNING)

from movieRec.movieRecommendation2.sharedLibraries.user_query_to_vector import (
    query_to_vectors,
)
from movieRec.config import load_config
from tavily import TavilyClient
from dotenv import load_dotenv
from pathlib import Path

# Load env configurations
current_file_path = Path(__file__).resolve()
project_root_dir = current_file_path.parent.parent.parent
env_path = project_root_dir / ".env"
load_dotenv(dotenv_path=env_path)
TAVILY_API_KEY = os.getenv("TAVILY_API_KEY")

def _clean_web_text(text: str) -> str:
    """
    Scrubs common website boilerplate text, scripts, and navigation artifacts
    from raw web content strings to optimize LLM input tokens.
    """
    if not text:
        return ""

    # 1. Compress multiple spaces and repeated newlines down to simple format
    text = re.sub(r"\s+", " ", text)

    # 2. List of common noisy boilerplate phrases found in scraped content windows
    noise_patterns = [
        r"skip to toolbar",
        r"about wordpress",
        r"wordpress\.org",
        r"documentation",
        r"support",
        r"feedback",
        r"log in",
        r"profile photo",
        r"written by:?.*",
        r"read more by.*",
        r"loading\s*\.\.\.",
        r"share:",
        r"leave a comment",
        r"you must be logged in to post a comment",
        r"no comments \s*»",
        r"don't be shy we want to hear from you",
        r"rss feed for comments.*",
        r"trackback url",
        r"see more comments",
        r"join us on instagram",
        r"credit\s*:\s*[^ ]+",
    ]

    # Combine patterns and execute a case-insensitive replacement pass
    combined_regex = re.compile(r"|".join(noise_patterns), re.IGNORECASE)
    cleaned_text = combined_regex.sub("", text)

    # 3. Final structural cleaning to pull out hanging whitespace leftovers
    cleaned_text = re.sub(r"\s*\[\s*\.\.\.\s*\]\s*", " [...] ", cleaned_text)
    cleaned_text = re.sub(r"\s+", " ", cleaned_text).strip()

    return cleaned_text

def find_movie_title(user_query: str) -> str:
    """
    Finds a movie based on semantic similarity using vector search and joins it
    with metadata from the cleaned_imdb table. Utilizes an integrated Tavily web
    search fallback loop to handle local data gaps.
    """
    print(f"--- Tool: find_movie_title tool called with user_query: {user_query} ---")
    start_time = time.perf_counter()

    # 1. Generate Query Vector
    bge_search_query = (
        f"Represent this sentence for searching relevant passages: {user_query}"
    )
    q_embeddings = query_to_vectors([bge_search_query])
    user_embeddings = q_embeddings[0]

    user_embeddings_list = (
        user_embeddings.tolist()
        if hasattr(user_embeddings, "tolist")
        else user_embeddings
    )

    # 2. Execute Local Vector Database Retrieval
    rows = []
    config = load_config()
    try:
        with psycopg2.connect(**config) as conn:
            with conn.cursor() as cursor:
                query = """
                    WITH unique_matches AS (
                        SELECT DISTINCT ON (e.tconst) 
                               c.primarytitle, c.genres, c.averagerating, 
                               COALESCE(c.plot_summary, c.plot_synopsis, 'No description available in local index.') AS plot_summary, 
                               c.duration, c.plot_synopsis,
                               e.embedding <=> %s::vector AS distance
                        FROM embeddings_table e
                        JOIN cleaned_imdb c ON e.tconst = c.tconst
                        ORDER BY e.tconst, e.embedding <=> %s::vector ASC
                    )
                    SELECT * FROM unique_matches
                    ORDER BY distance ASC
                    LIMIT 5;
                """
                cursor.execute(query, (user_embeddings_list, user_embeddings_list))
                rows = cursor.fetchall()
    except Exception as db_err:
        logging.getLogger(__name__).error(f"Database transaction failure: {db_err}")

    # 3. Gather Web Truth Context via Tavily API
    web_context_summary = ""
    try:
        tavily_client = TavilyClient(api_key=TAVILY_API_KEY)
        web_raw_data = tavily_client.search(
            query=f"{user_query} movie imdb",
            search_depth="advanced",
            max_results=3,
        )
        for w_idx, web_item in enumerate(web_raw_data.get("results", []), 1):
            raw_title = web_item.get("title", "No title")
            raw_url = web_item.get("url", "")
            raw_content = web_item.get("content", "")
            clean_content = _clean_web_text(raw_content)
            # Truncate to first 150 chars — enough for title identification, no noise
            short_content = (
                (clean_content[:150] + "...")
                if len(clean_content) > 150
                else clean_content
            )

            web_context_summary += (
                f"\nWeb Result #{w_idx}: '{raw_title}'\n"
                f"- URL: {raw_url}\n"
                f"- Snippet: {short_content}\n"
            )
    except Exception as api_err:
        logging.getLogger(__name__).error(f"Tavily lookup anomaly: {api_err}")
        web_context_summary = (
            "\nWeb fallback context unavailable due to API transmission error.\n"
        )

    # 4. Compile Standardized System Report Structure
    if rows:
        local_candidates_block = ""
        for idx, row in enumerate(rows, 1):
            title, genres, rating, summary, duration, synopsis, distance = row

            clean_summary = (
                (summary[:250] + "...") if summary and len(summary) > 250 else summary
            )
            clean_synopsis = (
                (synopsis[:400] + "...")
                if synopsis and len(synopsis) > 400
                else (synopsis or "N/A")
            )

            similarity_score = 1.0 / (1.0 + distance) if distance is not None else 0.0
            local_candidates_block += (
                f"\nCandidate #{idx}: '{title}' | Score: {similarity_score:.4f}\n"
                f"- Genres: {genres} | Rating: {rating} | Duration: {duration}\n"
                f"- Plot Summary: {clean_summary}\n"
                f"- Plot Synopsis: {clean_synopsis}\n"
            )
    else:
        print("--- Fallback to websearch due to RAG database absence ---")
        local_candidates_block = "\n⚠️ NOTICE: Local database query yielded 0 results. Rely exclusively on Live Web Context."

    # 5. Build Unified Layout Output
    unified_agent_context = (
        f'ORIGINAL USER REQUEST: "{user_query}"\n\n'
        f"--- WEB RESULTS (GROUND TRUTH) ---\n"
        f"{web_context_summary}\n"
        f"--- LOCAL DATABASE CANDIDATES (TOP 5) ---\n"
        f"{local_candidates_block}"
    )

    logging.getLogger(__name__).info(
        "`find_movie_title` executed successfully in %.3f ms",
        (time.perf_counter() - start_time) * 1000,
    )
    return unified_agent_context

"""
if __name__ == "__main__":
    result_report = find_movie_title(
        user_query="i am looking for a musical movie. It has a lot of singing and dancing. "
        "The male character plays piano. The female character is played by Emma Stone, "
        "male actor was Ryan something. In this movie, the female character wears yellow dress."
    )
    print("\n=== VERIFYING FINAL OUTPUT PAYLOAD ===")
    print(result_report)
"""

# output of user query:
"""
=== VERIFYING FINAL OUTPUT PAYLOAD ===
=== SYSTEM RETRIEVAL REPORT ===
ORIGINAL USER REQUEST: "i am looking for a musical movie. It has a lot of singing and dancing. The male character plays piano. The female character is played by Emma Stone, male actor was Ryan something. In this movie, the female character wears yellow dress."

--- LIVE INTERNET TRUTH CONTEXT ---
Web Source #1: Emma Stone and Ryan Gosling sing and dance together in La La Land -> Two of my favourite actors are getting together again, in a musical. (Who didn’t love Emma Stone and Ryan Gosling in Crazy Stupid Love?). The trailer has me hooked. Ticking all the boxes with moody magical visuals, some cool outfits and a little bit of dancing. Also, I mean, nothing is more irresistible than Ryan Gosling tinkling on the piano (okay, except for maybe a grilled cheese toastie). The movie is directed by Whiplash writer/director Damien Chazelle. If that’s anything to go by then we certainly won’t be in for your average musical. [...]
Web Source #2: La La Land - Wikipedia -> MovieWeb ranked the film number 2 on its list of the "Best Movie Musicals of the 21st Century So Far," in 2022 as well. In 2023, it ranked it number 3 on its list of the "15 Greatest Movies About Jazz" and number 1 on its list of the "Best Modern Movies Shot on Film." It also ranked number 2 on Teen Vogue's list of "The 45 Best Dance Movies of All Time." The film ranked number 15 on Collider "Collider (website)")'s list of the "30 Best Musicals of All Time," with Jeremy Urquhart writing, "It works as a modern update/homage to classic Hollywood musicals that were popular in the 1950s without ever feeling derivative or mocking, and Emma Stone and Ryan Gosling in the lead roles both give great performances that are up there with the best of their respective careers." [...] Emma Stone plays Mia, an aspiring actress in Los Angeles. Stone has loved musicals since she saw Les Misérables "Les Misérables (musical)") when she was eight years old. She said "bursting into song has always been a real dream of mine", and her favorite film is the 1931 Charlie Chaplin romantic comedy City Lights. She studied pom dancing as a child, with a year of ballet. She moved to Hollywood with her mother at age fifteen to pursue a career, and struggled constantly to get an audition during her first year. When she did, she often was turned away after singing or saying just one line. Stone drew from her own experiences for her character of Mia, and some were added into the film. [...] much of the public criticism was towards the film being "a little dull", the two leads' singing and dancing being considered unexceptional, and the lack of nuance in Stone's character, with Gosling's occasionally seen as insufferable.
Web Source #3: La La Land Review: Emma Stone and Ryan Gosling Star in New Movie Musical -> In possibly the most sublime moment in the often sublime modern movie musical La La Land, directed by Damien Chazelle, Emma Stone is out to dinner in Los Angeles (she’s with a rather colorless date and a similarly colorless couple). A strain of piano music comes trickling in from another room. Stones’ eyes, which even when looking at nothing suggest two brilliant beacons on a smallish lighthouse, brighten in recognition — if anything, her whole body seems to brighten. We watch her lifted from the torpor of dinner and onto a higher plane by love: for the piano theme, and for the pianist playing it. [...] At another point in the film, she and that pianist, Ryan Gosling, will literally be lifted up into sky as a sort of astral consummation of their relationship. That’s lovely, too, of course, but it’s a special effect. What Stone accomplishes in that moment in the restaurant is done with more ineffable magic, a combination of her own airy skill and the love the camera can’t help but la-la-lavish on her: She doesn’t sing, but she doesn’t have to. It’s as if she herself were the melody. RELATED VIDEO: Ryan Gosling & Emma Stone Discuss ‘La La Land’ Fan Reactions [...] Any good movie musical (and quite a few bad ones) will make us accept the pretense that a song rises in the body like sap in a tree and then blooms as flowers and leaves. But, as La La Land demonstrates, a movie musical starring Emma Stone has imaginative and emotional powers beyond even that. La La isn’t revolutionary — it has its share of retro pleasures. A bittersweet variation on boy-meets-girl, it consciously mines movie-musical history and conventions. The opening dance number, set in a traffic jam on the freeway, pays homage to the 1967 Catherine Deneuve musical The Young Girls of Rochefort (overall, the movie owes even more to Deneuve’s Umbrellas of Cherbourg). And there’s a lavish moment near the end that recalls the dreamy swoon of An American in Paris.

--- LOCAL DATABASE CANDIDATES (TOP 5) ---

Candidate #1: 'Emma' | Score: 0.7526
- Genres: Musical | Rating: 7.5 | Duration: None
- Plot Summary: No description available in local index.
- Plot Synopsis: N/A

Candidate #2: 'Pianist' | Score: 0.7506
- Genres: Musical,Romance | Rating: 4.6 | Duration: None
- Plot Summary: No description available in local index.
- Plot Synopsis: N/A

Candidate #3: 'La La Land' | Score: 0.7490
- Genres: Comedy,Drama,Music | Rating: 8.0 | Duration: 2h 8min
- Plot Summary: Aspiring actress serves lattes to movie stars in between auditions and jazz musician Sebastian scrapes by playing cocktail-party gigs in dingy bars. But as success mounts, they are faced with decisions that fray the fragile fabric of their love affai...
- Plot Synopsis: During the opening credits, the movie we are viewing is said to have been filmed in CINEMASCOPE (like the old-time musicals) and then the screen expands from box format to wide. We find ourselves on the 105/110 interchange in Los Angeles. People listen to various forms of music in their cars. Then one woman gets out of her vehicle and starts singing ANOTHER DAY OF SUN to camera (à la a musical), a...

Candidate #4: 'The Piano' | Score: 0.7468
- Genres: Drama,Music,Romance | Rating: 7.5 | Duration: 2h 1min
- Plot Summary: It is the mid-nineteenth century. Ada cannot speak and she has a young daughter, Flora. In an arranged marriage she leaves her native Scotland accompanied by her daughter and her beloved piano. Life in the rugged forests of New Zealand's North Island...
- Plot Synopsis: The Piano tells the story of a speechless Scotswoman, Ada McGrath (Holly Hunter), whose father sells her into marriage to a New Zealand frontiersman, Alistair Stewart (Sam Neill). She is shipped off along with her young daughter, Flora McGrath (Anna Paquin). Ada has not spoken a word since she was six years old, expressing herself instead through her piano playing and through sign language for whi...

Candidate #5: 'Piano Is Her Name' | Score: 0.7429
- Genres: Crime | Rating: 6.941349 | Duration: None
- Plot Summary: No description available in local index.
- Plot Synopsis: N/A
"""
