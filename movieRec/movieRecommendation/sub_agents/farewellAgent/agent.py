"""Agent module for farewell agent"""
from google.adk.agents import Agent
from .sayByeBye import sayByeBye  # renamed file to match
from .prompt import FAREWELL_AGENT_INSTRUCTION

farewell_agent = Agent(
    model="gemini-2.5-flash",
    name="farewell_agent",
    description="Politely says goodbye to users using their name.",
    instruction=FAREWELL_AGENT_INSTRUCTION,
    tools=[sayByeBye]  # plain function works fine
)