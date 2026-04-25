"""Agent module for find_movie_title agent"""

from google.adk.agents import Agent
from google.adk.tools import google_search
from .get_movie_title import get_movie_title
from movieRecommendation.sharedLibraries.user_query_to_vector import user_query_to_vectors
from google.adk.tools.agent_tool import AgentTool
from .prompt import FIND_MOVIE_TITLE_AGENT_INSTRUCTION

google_search_agent = Agent(
    model="gemini-2.5-flash",
    name="google_search_agent",
    description="Fill missing movie info and validate semantic search results using web search.",
    instruction="""
    You receive candidate movies from semantic search.
    For each movie:
    - If any field is missing or "N/A" → search Google to fill it
    - Validate if the movie actually matches the original user description
    Return enriched, accurate movie list.
    """,
    tools=[google_search],
    output_key="movie_titles_found_final"
)
google_search_agent_tool = AgentTool(agent=google_search_agent, skip_summarization=True)

find_movie_title_agent = Agent(
    model="gemini-2.5-flash",
    name="find_movie_title_agent",
    description="Find movies matching user's natural language description using semantic search.",
    instruction=FIND_MOVIE_TITLE_AGENT_INSTRUCTION,
    tools=[
        user_query_to_vectors,
        get_movie_title,
        google_search_agent_tool
    ],
    output_key="movie_titles_found"
)
