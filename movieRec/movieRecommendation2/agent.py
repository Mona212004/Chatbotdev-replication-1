"""Agent module for main orchestrator agent"""

# api key is with personal email
# Ability:
# agent greet
# update and remove preferences
# agent find movie title given movie attributes(genre, plot summary, plot synopsis) (vector similarity search with embeddings + google search if not found in db)
# google search to fill missing movie info + validate semantic search results if movie does not exist in db
# retrieve movie info from db (duration, genres, plot summary, rating, plot synopsis) given movie title (find tconst given title then retrieve)
# agent receommend movies given user query vector, vector similarity search with embeddings_table.embeddings
# recommend movies given averagerating (real num), genres str, duration str

from .prompt5 import ORCHESTRATOR_AGENT_INSTRUCTION
from google.adk.agents import LlmAgent
from google.adk.models.lite_llm import LiteLlm

import warnings

warnings.filterwarnings("ignore")

import logging

logging.basicConfig(level=logging.ERROR)

from .test_models import root_model
from .tools_dir.greet_dir.greet import sayHello
from .tools_dir.pref_manager_dir.preference_manager import (
    get_preferences,
    update_preferences,
    remove_preferences,
    remove_all_preferences,
)
from .tools_dir.movie_finder_dir.find_movie_tool import find_movie_title
from .tools_dir.info_retriever_dir.retrieve_movie_info import get_movie_info
from .tools_dir.recommender_dir.recommender import (
    recommend_similar_to_movie,
    recommend_from_preferences,
)

# debugging: see the request sent to the Ollama server

import os
from pathlib import Path
from dotenv import load_dotenv

# get absolute path of this file
current_file_path = Path(__file__).resolve()
# go up to movieRecommendation2 dir (adjust levels as needed)
project_root_dir = current_file_path.parent
env_path = project_root_dir / ".env"
load_dotenv(dotenv_path=env_path)

# if os.getenv("INTEGRATION_TESTING") == "TRUE": #for google search fallback

# use LLM
root_agent = None
runner_root = None  # initialize runner

# 1. Determine provider and model dynamically
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "ollama")

if LLM_PROVIDER == "groq":
    # On Render, ROOT_MODEL is set to "qwen/qwen3.6-27b"
    active_model = os.getenv("ROOT_MODEL", "qwen/qwen3.6-27b")
    llm_instance = LiteLlm(
        model=active_model,
        api_base="https://api.groq.com/openai/v1",
        api_key=os.getenv("GROQ_API_KEY"),
        custom_llm_provider="openai",
        temperature=0,
        reasoning_effort="none",  # turns off qwen3.6's thinking mode entirely — root fix for both leakage and latency
        allowed_openai_params=[
            "reasoning_effort"
        ],  # tells litellm this is a valid pass-through param for this OpenAI-compatible endpoint
        extra_body={
            "reasoning_format": "hidden"
        },  # reasoning_format isn't a real openai SDK kwarg, so it has to go through extra_body to reach Groq's raw request body
    )
else:
    # Keeps your local setup working exactly as it is now
    from .test_models import root_model

    active_model = os.getenv("ROOT_MODEL", root_model)
    llm_instance = LiteLlm(
        model=active_model,
        api_base="http://localhost:11434",
        custom_llm_provider="ollama_chat",
        temperature=0,
    )

# 2. Initialize the Orchestrator Agent using the correct cloud/local model instance
try:
    root_agent = LlmAgent(
        model=llm_instance,  # Directly feeds the dynamic configuration here
        name="root_agent",
        description="The main coordinator agent. Your primary task is to delegate tasks to sub-agents and tools based on user query.",
        instruction=ORCHESTRATOR_AGENT_INSTRUCTION,
        tools=[
            sayHello,
            get_preferences,
            update_preferences,
            remove_preferences,
            remove_all_preferences,
            find_movie_title,
            get_movie_info,
            recommend_similar_to_movie,
            recommend_from_preferences,
        ],
    )
except Exception as e:
    print(f"Error initializing root agent: {e}")
