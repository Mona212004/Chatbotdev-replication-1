"""Agent module for main orchestrator agent"""
from google.adk.agents import Agent
from .prompt import ORCHESTRATOR_AGENT_INSTRUCTION
from .sub_agents.farewellAgent.agent import farewell_agent
from .sub_agents.find_movie_title_agent.agent import find_movie_title_agent
from .sub_agents.greetingAgent.agent import greeting_agent
from .sub_agents.recAgent.agent import recommendation_agent
from .sub_agents.retrieve_from_db_agent.agent import retrieve_from_db_agent
from google.adk.planners import PlanReActPlanner
from google.genai import types

root_agent = Agent(
        model="gemini-2.5-flash",
        name="root_agent",
        description="Main orchestrator that manages movie greetings, search, recommendations, and information retrieval.",
        instruction=ORCHESTRATOR_AGENT_INSTRUCTION,
        planner=PlanReActPlanner(),
        sub_agents=[
            greeting_agent,
            farewell_agent,
            find_movie_title_agent,
            recommendation_agent,
            retrieve_from_db_agent
        ]
    )

#api key is with personal email

