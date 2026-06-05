# create the agent and test out the updated prompt
from google.adk.agents import LlmAgent
from google.adk.models.lite_llm import LiteLlm

import warnings
warnings.filterwarnings("ignore")
import logging
logging.basicConfig(level=logging.ERROR)

from ...test_models import movie_finder_model
from .find_movie_tool import find_movie_title
from .prompt3 import movie_finder_instructions

import os

# for running movie finder agent on its own
# from movieRec.movieRecommendation2.test_models import movie_finder_model

# use LLM
movie_finder_agent = None
try:
    movie_finder_agent = LlmAgent(
        model=LiteLlm(
            model=movie_finder_model,
            api_base="http://localhost:11434",
            #api_key=os.environ["GROQ_API_KEY"],
            temperature=0,
        ),
        name="movie_finder_agent",
        description="You are a movie finder agent that finds a movie based on user's description of the movie.",
        instruction=movie_finder_instructions,
        tools=[find_movie_title],
        #output_key="movie_finder_response",
    )
except Exception as e:
    print(f"Error initializing movie finder agent: {e}")

# for running movie finder agent on its own
# root_agent = movie_finder_agent
