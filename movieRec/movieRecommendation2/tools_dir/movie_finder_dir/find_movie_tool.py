import os
import time
import logging
import re
from typing import Any, Optional, List
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
    if not text:
        return "N/A"
    text = re.sub(r"<script\b[^<]*?>([\s\S]*?)</script>", "", text)
    text = re.sub(r"<style\b[^<]*?>([\s\S]*?)</style>", "", text)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def find_movie_title(user_query: str) -> str:
    """
    Finds a movie title based on a description or attributes using a real-time search engine.
    """
    print(f"--- Tool: find_movie_title tool called with query: {user_query} ---")
    start_time = time.perf_counter()

    try:
        if not TAVILY_API_KEY:
            return "Error: Missing configuration settings. Tavily API Key not found in .env profile."

        tavily_client = TavilyClient(api_key=TAVILY_API_KEY)
        search_response = tavily_client.search(
            query=f"{user_query} movie site:imdb.com",
            search_depth="advanced",
            max_results=2,
            include_raw_content=True,
        )

        web_reports = ""
        if search_response and "results" in search_response:
            for i, res in enumerate(search_response["results"], 1):
                url = res.get("url", "")
                # Skip generic IMDB lists entirely
                if "imdb.com/list/" in url:
                    continue
                clean_body = _clean_web_text(
                    res.get("raw_content", res.get("content", ""))
                )[:600]
                web_reports += f"\nWeb Candidate #{i}:\n- Title/Context: {res.get('title')}\n- URL: {res.get('url')}\n- Text Fragment: {clean_body}...\n"

        return (
            f"SYSTEM RETRIEVAL REPORT:\n"
            f"Flipped to active real-time web verification matrix.\n"
            f"Raw Search Results:\n{web_reports}"
        )
    except Exception as web_err:
        return (
            f"Failure: Real-time search engine tracking encountered an issue: {web_err}"
        )


if __name__ == "__main__":
    result_report = find_movie_title(
        user_query="i am looking for a musical movie. It has a lot of singing and dancing. "
        "The male character plays piano. The female character is played by Emma Stone, "
        "male actor was Ryan something. In this movie, the female character wears yellow dress."
    )
    print("\n=== VERIFYING FINAL OUTPUT PAYLOAD ===")
    print(result_report)
