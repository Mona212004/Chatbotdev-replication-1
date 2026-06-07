# preference management agent
import os
os.environ["LITELLM_SKIP_MODEL_INFO_CHECK"] = "True"

from typing import Optional, Any, List

# for running preference agent agent on its own
# from movieRec.movieRecommendation2.entities.user2 import (UserFunctions, User, MoviePreferences,)
# from movieRec.movieRecommendation2.test_models import preference_manager_model

# for being called to root agent
from ...entities.user2 import UserFunctions, MoviePreferences

func = UserFunctions()

# tool
def get_preferences(user_id: Optional[Any] = None) -> str:
    """
    Retrieves the current movie preferences for a specific user.

    Args:
        user_id (Optional[Any]): The numeric ID of the user extracted from history.
    """
    if user_id is not None:
        val = str(user_id).lower().strip()
        try:
            user_id = int(val)
        except ValueError:
            user_id = None

    print(f"--- Tool: get_preferences tool called with user_id: {user_id} ---")

    if user_id is None or user_id == 0:
        return "Error: User ID is required to fetch preferences. Please log in."

    # FIX HERE: Changed get_user_by_id to get_user
    User = func.get_user(current_user_id=user_id)

    if User is None:
        return f"Error: No user found with ID {user_id}."
    else:
        return f"User preferences for user ID {user_id} are: {User.preferences}"

def update_preferences(
    user_id: Optional[Any] = None,
    liked_genres: Optional[List[str]] = None,
    movie_interests_titles: Optional[List[str]] = None,
) -> str:
    """
    Updates the movie preferences for a specific user in the database.
    This function is designed to be called by the preference manager agent using user IDs
    and preference list categories extracted directly from the conversation history logs.

    Args:
        user_id (Optional[Any]): User ID extracted from the conversation history log.
        liked_genres (Optional[List[str]]): List of genres the user likes.
        movie_interests_titles (Optional[List[str]]): Specific movie titles the user likes.

    Returns:
        str: Message indicating the result of the update operation.
    """
    if user_id is not None:
        val = str(user_id).lower().strip()
        if val in ["0", "forgot", "i forgot", "none", "new account"]:
            user_id = 0
        else:
            try:
                user_id = int(val)
            except ValueError:
                user_id = None  # Fallback to check by name

    print(f"--- Tool: update_preferences tool called with user_id: {user_id} ---")

    if user_id is None or user_id == 0:
        return "Error: User ID is required to update preferences. Please provide your User ID."

    # Instantiate your database-expected object safely inside the execution logic
    prefs_payload = MoviePreferences(
        liked_genres=liked_genres or [],
        movie_interests_titles=movie_interests_titles or [],
    )

    # Pass the packed dataclass object to your backend function to match remove_preferences
    User = func.update_user_preferences(user_id, prefs_payload)

    if User is None:
        return f"Error: No user found with ID {user_id}. Cannot update preferences."
    else:
        return f"User preferences for user ID {user_id} have been successfully updated: {User.preferences}"

def remove_preferences(
    user_id: Optional[Any] = None,
    liked_genres: Optional[List[str]] = None,
    movie_interests_titles: Optional[List[str]] = None,
) -> str:
    """
    Remove specific elements from the user's preferences in the database.
    This function is designed to be called by the preference manager agent using user IDs
    and preference list categories extracted directly from the conversation history logs.

    Behavior:
    - If user_id is None or 0: Returns an error message indicating that user_id is required.
    - If user_id is provided: Retrieves the existing user by ID and processes the preference removals.

    Args:
        user_id (Optional[Any]): User ID extracted from the conversation history log.
        liked_genres (Optional[List[str]]): Specific liked genres to remove.
        movie_interests_titles (Optional[List[str]]): Specific movie titles to remove from interests.

    Returns:
        str: Message indicating the result of the remove operation.
    """
    if user_id is not None:
        val = str(user_id).lower().strip()
        if val in ["0", "forgot", "i forgot", "none", "new account"]:
            user_id = 0
        else:
            try:
                user_id = int(val)
            except ValueError:
                user_id = None  # Fallback to check by name

    print(f"--- Tool: remove_preferences tool called with user_id: {user_id} ---")

    if user_id is None or user_id == 0:
        return "Error: User ID is required to remove preferences. Please provide your User ID."

    # Pack the flat arguments cleanly into the MoviePreferences dataclass/model
    # expected by your backend DB layout execution layers
    preferences_to_remove = MoviePreferences(
        liked_genres=liked_genres or [],
        movie_interests_titles=movie_interests_titles or [],
    )

    # Safely execute removal with the structured object
    User = func.remove_preferences(user_id, preferences_to_remove)
    if User is None:
        return f"Error: No user found with ID {user_id}. Cannot remove preferences."
    else:
        return f"User preferences for user ID {user_id} have been successfully removed: {User.preferences}"

def remove_all_preferences(user_id: Optional[Any] = None) -> str:
    """
    Remove all elements from the user's preferences in the database automatically.

    Args:
        user_id (Optional[Any]): User ID extracted from the conversation history log.

    Returns:
        str: Message indicating the result of the remove operation.
    """
    if user_id is not None:
        val = str(user_id).lower().strip()
        if val in ["0", "forgot", "i forgot", "none", "new account"]:
            user_id = 0
        else:
            try:
                user_id = int(val)
            except ValueError:
                user_id = None  # Fallback to check by name

    print(f"--- Tool: remove_all_preferences tool called with user_id: {user_id} ---")

    if user_id is None or user_id == 0:
        return "Error: User ID is required to remove preferences. Please provide your User ID."

    # Using lowercase 'user' for proper convention
    user = func.get_user(current_user_id=user_id)
    preferences_to_remove = (
        user.preferences
        if user and user.preferences
        else MoviePreferences(liked_genres=[], movie_interests_titles=[])
    )

    user = func.remove_preferences(user_id, preferences_to_remove)
    if user is None:
        return f"Error: No user found with ID {user_id}. Cannot remove preferences."
    else:
        return f"User preferences for user ID {user_id} have been successfully removed: {user.preferences}"

# when calling remove preferences or update preferences, the preferences must be wrapped in MoviePreferences()
# the preferences keys are specifically liked_genres, movie_interests_titles

# test tool
# if __name__ == "__main__":
# User = update_preferences(33, new_preferences=MoviePreferences(liked_genres=["Comedy"]),)
# User = remove_preferences(33, preferences_to_remove=MoviePreferences(liked_genres=["roMance"],))
# print(User)

