"""Agent module for greeting agent"""
from google.adk.agents import Agent
from .sayHello import (
    save_user_name,
    ask_for_name,
    ask_for_genres,
    create_and_greet_new_user,
    greet_returning_user
)
from .prompt import GREETING_AGENT_INSTRUCTION

greeting_agent = Agent(
    model="gemini-2.5-flash",
    name="greeting_agent",
    description="Greets users by name, remembers them across sessions via username.",
    instruction=GREETING_AGENT_INSTRUCTION,
    tools=[
        ask_for_name,
        save_user_name,
        ask_for_genres,
        create_and_greet_new_user,
        greet_returning_user
    ]
)

