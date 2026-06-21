# greet agent, this version works with groq model
import os
os.environ["LITELLM_SKIP_MODEL_INFO_CHECK"] = "True"

from typing import Optional, Any

# for running greeting agent on its own
# from movieRec.movieRecommendation2.entities.user2 import (UserFunctions, User, MoviePreferences,)
# from movieRec.movieRecommendation2.test_models import greeting_model

# for being called to root agent
from movieRecommendation2.entities.user2 import UserFunctions, User, MoviePreferences

from google.adk.agents import LlmAgent
from google.adk.models.lite_llm import LiteLlm

func = UserFunctions()

# tool
def sayHello(username: str, user_id: Optional[Any] = None) -> str:
    """
    Greets the user and manages their account in the database.

    Behavior:
    - If user_id is None:
        - Username not found in DB: creates a new account.
        - Username found in DB: prompts user to provide their User ID.
    - If user_id is 0: user cannot remember their ID — creates a new account.
    - If user_id is provided (non-zero): retrieves existing user directly by ID and welcomes them back.

    Args:
        username (str): Name of the user provided in chat.
        user_id (Optional[Any]): User ID extracted from the current chat session.
                                 None = first interaction, 0 = wants new account.
    Returns:
        str: Greeting message or prompt asking for user_id.

    Example:
        sayHello("Alice")        # no user_id → checks username first
        sayHello("Alice", 10)    # user_id provided → retrieves returning user by ID
        sayHello("Alice", 0)     # user_id=0 → creates new account
    """

    if user_id is not None:
        val = str(user_id).lower().strip()
        if val in ["none", "null", ""]:
            # The model sometimes serializes "no ID yet" as the literal string "None"
            # instead of a true null. Treat it the same as real None so we still look
            # up the existing account by username instead of creating a duplicate.
            user_id = None
        elif val in ["0", "forgot", "i forgot", "new account"]:
            user_id = 0
        else:
            try:
                user_id = int(val)
            except ValueError:
                user_id = None  # Fallback to check by name
    #  print(f"--- Tool: sayHello tool called with username: {username}, user_id: {user_id} ---")
    #  print(f"--- Tool: sayHello tool called with username: {username}, user_id: {user_id} ---")

    if user_id is None:
        # print("No user_id provided. Check if username already exists in the database to avoid duplicate accounts.")
        User = func.get_user_by_name(username)
        if User is None:
            User = func.create_new_user(user_name=username)
            return f"AUTH_SUCCESS: User {User.user_name}! Welcome to MovieRec! We have created a new account for you, your User ID is [{User.user_id}]."
        else:
            # username exists, ask agent to prompt user for their ID
            # agent will call sayHello again with user_id once user provides it
            # or call sayHello with user_id=0 if user wants a new account
            return (
                f"Welcome! We found an existing account for '{username}'. "
                f"Please provide your User ID to access it. "
                f"If you don't remember your ID or want a new account, reply with 'User ID = 0'."
            )
    elif user_id == 0:
        # user cannot remember their ID — create new account
        new_user = func.create_new_user(user_name=username)
        return f"AUTH_SUCCESS: User {new_user.user_name}! A new account has been created for you. Your new User ID is [{new_user.user_id}]. Please remember your user ID."
    else:
        User = func.get_user(current_user_id=user_id)
        if User is None:
            # This case should ideally not happen if user_id is correctly managed in the session
            return f"Error: No user found with User ID: {user_id}. Please check your session management."
        return f"AUTH_SUCCESS: User {User.user_name}, User ID: [{User.user_id}]! Your preferences are {User.preferences}."

# test tool
# if __name__ == "__main__":
# print(sayHello("Alex"))
# print(sayHello("Alice")) # new user, creates account
# print(sayHello("Alice", 0)) # existing username, prompts for ID
# print(sayHello("Alice",20)) #D:\cpython -m movieRec.movieRecommendation2.subagents.greet hatbotdev_essential> python -m movieRec.movieRecommendation2.subagents.greet works
