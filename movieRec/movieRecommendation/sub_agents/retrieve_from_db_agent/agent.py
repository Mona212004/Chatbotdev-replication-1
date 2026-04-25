"""Agent module for retrieve_from_db agent"""
from google.adk.agents import Agent
from .get_movie_duration import get_movie_duration
from .get_movie_genres import get_movie_genres
from .get_movie_plot_summary import get_movie_plot_summary
from .get_movie_plot_synopsis import get_movie_plot_synopsis
from .get_movie_rating import get_movie_rating
from .movieIsExist import check_if_movie_exists_in_db
from .prompt import RETRIEVE_FROM_DB_AGENT_INSTRUCTION
from google.adk.planners import PlanReActPlanner
from google.adk.tools import google_search
from google.adk.tools.agent_tool import AgentTool

google_search_agent = Agent(
    model="gemini-2.5-flash",
    name="fallback_search_agent",
    description="Fill missing movie information using web search.",
    instruction="""
    You receive a list of movie dictionaries from the database retrieval agent.
    Each movie has fields: title, exists_in_db, genres, duration, rating, summary, synopsis.
    Your task:
    - For movies where exists_in_db is False OR any field is missing/None → use google_search to find the correct value
    - For movies that exist but have missing fields → fill them
    - Return the complete, enriched list
    
    Use precise queries like "{title} movie genres" or "{title} IMDb rating"
    """,
    tools=[google_search],
    output_key="movie_info_final"
)
google_search_tool = AgentTool(
    agent=google_search_agent,
    skip_summarization=True
)

retrieve_from_db_agent = Agent(
    model="gemini-2.5-flash",
    name="retrieve_from_db_agent",
    description="Retrieve movie info from DB, then fallback to web if needed.",
    instruction=RETRIEVE_FROM_DB_AGENT_INSTRUCTION,
    planner=PlanReActPlanner(),
    tools=[
        check_if_movie_exists_in_db,
        get_movie_genres,
        get_movie_duration,
        get_movie_rating,
        get_movie_plot_summary,
        get_movie_plot_synopsis,
        google_search_tool  
    ],
    output_key="movie_info_retrieved_from_db"
)