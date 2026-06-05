#do not run, not used to test, use adk run instead
import asyncio
from google.adk.agents import LlmAgent
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from movieRec.movieRecommendation2.subagents.greet.agent import greeting_agent
from movieRec.movieRecommendation2.test_models import greeting_model
from google.genai import types
import json

APP_NAME = "testing_greeting_agent_app"
USER_ID = "test_user_1"
SESSION_ID_TOOL_AGENT = "session_greeting_agent"

session_service = InMemorySessionService()

# create a runner for greeting agent
greeting_runner = Runner(
    agent=greeting_agent,
    app_name=APP_NAME,
    session_service=session_service
)


async def call_agent_and_print(
    runner_instance: Runner, agent_instance: LlmAgent, session_id: str, query_json: str):
    """Sends a query to the specified agent/runner and prints results."""
    print(f"\n>>> Calling Agent: '{agent_instance.name}' | Query: {query_json}")
    user_content = types.Content(role='user', parts=[types.Part(text=query_json)])
    final_response_content = "No final response received."

    async for event in runner_instance.run_async(user_id=USER_ID, session_id=session_id, new_message=user_content):
        # print(f"Event: {event.type}, Author: {event.author}")
        if event.is_final_response() and event.content and event.content.parts:
            final_response_content = event.content.parts[0].text
    print(f"<<< Final Response from '{agent_instance.name}': {final_response_content}")

    current_session = await session_service.get_session(app_name=APP_NAME, user_id=USER_ID, session_id=session_id)
    stored_output = current_session.state.get(agent_instance.output_key)

    # Pretty print if the stored output looks like JSON (likely from output_schema)
    print(f"--- Session State ['{agent_instance.output_key}']: ", end="")
    try:
        # Attempt to parse and pretty print if it's JSON
        parsed_output = json.loads(stored_output)
        print(json.dumps(parsed_output, indent=2))
    except (json.JSONDecodeError, TypeError):
        # Otherwise, print as string
        print(stored_output)
    print("-" * 30)

async def main():
    # Create separate sessions for clarity, though not strictly necessary if context is managed
    print("--- Creating Sessions ---")
    await session_service.create_session(app_name=APP_NAME, user_id=USER_ID, session_id=SESSION_ID_TOOL_AGENT)

    print("--- Testing Agent with Tool ---")
    # await call_agent_and_print(greeting_runner, greeting_agent, SESSION_ID_TOOL_AGENT, "Hi I am Ashley") #new user

    # await call_agent_and_print(greeting_runner, greeting_agent, SESSION_ID_TOOL_AGENT, "Hi I am Ashley, My user id is 24")

    # await call_agent_and_print(greeting_runner, greeting_agent, SESSION_ID_TOOL_AGENT, "Hi I am Ashley") #exist, ask for id again, enters idd
    # await call_agent_and_print(greeting_runner, greeting_agent, SESSION_ID_TOOL_AGENT, "My user id is 24")

    await call_agent_and_print(greeting_runner, greeting_agent, SESSION_ID_TOOL_AGENT, "Hi I am Ashley") #exist, ask for id again, no id
    await call_agent_and_print(greeting_runner, greeting_agent, SESSION_ID_TOOL_AGENT, "User ID = 0")

    # await call_agent_and_print(greeting_runner, greeting_agent, SESSION_ID_TOOL_AGENT, "Hi I am Ashley") #exist, ask for id again, no id
    # await call_agent_and_print(greeting_runner, greeting_agent, SESSION_ID_TOOL_AGENT, "I do not remember my user id.")

    # await call_agent_and_print(greeting_runner, greeting_agent, SESSION_ID_TOOL_AGENT, "Hi I am Bob")


if __name__ == "__main__":
    asyncio.run(main())

# run ollama serve before running this script
# (.venv) PS D:\chatbotdev_essential> adk run movieRec/movieRecommendation2/subagents/greet, python script not related to adk run
