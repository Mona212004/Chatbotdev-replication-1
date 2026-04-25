# greetingAgent/sayHello.py
from movieRecommendation.sub_agents.greetingAgent.checkIfUserExist import checkUserExist
from google.adk.tools import ToolContext
from movieRecommendation.entities.user import User

def save_user_name(tool_context: ToolContext, user_name: str) -> str:
    """Internal tool: saves the extracted name. 
    Args:
        user_name: The name of the user extracted from conversation.
    """
    print(f"---Tool: save_user_name called for {user_name}---")
    # Explicitly save to state so other tools can see it
    tool_context.state["pending_name"] = user_name.capitalize()
    return f"Successfully recorded name as {user_name}."

# Tool 1: Ask for name (first contact)
def ask_for_name(tool_context: ToolContext) -> str:
    """Initial greeting: asks the user for their name."""
    print("---Tool: ask_for_name called---")
    return "Hello! I'm your movie recommendation assistant. What's your name so I can personalize your experience?"


# Tool 2: Ask for genres after name is given
def ask_for_genres(tool_context: ToolContext) -> str:
    """Asks for favorite genres after name is known."""
    print("---Tool: ask_for_genres called---")
    name = tool_context.state.get("pending_name")
    
    # This was failing because state was empty
    if not name:
        return "I'm sorry, I missed your name. Could you please tell me again?"
        
    return f"Great to meet you, {name}! What are your favorite movie genres?"


# Tool 3: Create new user after genres provided
def create_and_greet_new_user(tool_context: ToolContext, genres: list[str]) -> str:
    """Creates new user and gives final greeting.
    Args:
        genres: A list of genres extracted from user input (e.g. ["Action", "Sci-Fi"])
    """
    print(f"---Tool: create_and_greet_new_user called with {genres}---")

    pending_name = tool_context.state.get("pending_name")
    
    # Use the argument passed by the LLM directly
    if not pending_name or not genres:
        return "Hmm, something went wrong. Let's start over — what's your name?"


# Tool 4: Greet returning user using checkUserExist()
def greet_returning_user(tool_context: ToolContext) -> str:
    """Greets returning user by loading existing profile."""
    print("---Tool: greet_returning_user called---")

    name = tool_context.state.get("pending_name")
    if not name:
        return "Welcome back! What's your name so I can load your profile?"

    user = checkUserExist(name)
    if not user:
        return f"I couldn't find a profile for '{name}'. Let's create one — what are your favorite genres?"

    tool_context.state["current_user"] = user
    tool_context.state.pop("pending_name", None)

    liked = user.get('preferences', {}).get('liked_genres', [])
    prefs = ', '.join(liked) if liked else 'none yet'
    return f"Welcome back, {user['user_name']}! Your movie preferences: {prefs}. How can I help you today?"