# farewellAgent/sayByeBye.py
from google.adk.tools import ToolContext

def sayByeBye(tool_context: ToolContext, user_name: str = "") -> str:
    """Provides a warm farewell using the user's name from state or parameter."""
    print("---Tool: sayByeBye called---")
    
    # Prefer name from persistent state (set by greeting agent)
    current_user = tool_context.state.get("current_user")
    if current_user and current_user.get("user_name"):
        name = current_user["user_name"]
    else:
        name = user_name.strip() or "friend"
    
    return f"Goodbye {name}! Thanks for chatting about movies. Come back anytime! 🎬👋"