import gradio as gr
import requests

# Your live production backend URL on Render
BACKEND_URL = "https://movie-recommender-api-6oqf.onrender.com/chat"


def chat_with_agent(user_message, history):
    try:
        clean_message = user_message.strip()
        if not clean_message:
            return "Please type a message to chat with the agent."

        # The Fix: Wrap the input in a standard JSON key-value dictionary object
        # This gives the validation layer the structure it needs to run .get() safely!
        payload = {"message": clean_message}

        response = requests.post(BACKEND_URL, json=payload)

        if response.status_code == 200:
            agent_reply = response.json()

            # If the backend returns a dictionary response object, extract the text string
            if isinstance(agent_reply, dict):
                return agent_reply.get(
                    "response", agent_reply.get("output", str(agent_reply))
                )
            return agent_reply

        else:
            return f"❌ Backend Error {response.status_code}: {response.text}"

    except Exception as e:
        return f"🔌 Connection Error: Could not reach Render server. Details: {str(e)}"


# Define the exact testing flow from your local ADK logs as rapid-click examples
test_examples = [
    "hi i am hannah montanah, user id = 79",
    "what are my current preferences?",
    "i do not like action movies anymore. Now i like animated movies like 'tinklebell'.",
    "remove all my preferences",
]

# Build a polished, custom UI container matching your theme
with gr.Blocks() as demo:  # Removed theme parameter from here
    gr.Markdown("# 🎬 AI Movie Recommender Chatbot")
    gr.Markdown(
        "**Backend Status:** Live on Render Cloud Engine | **Database Layer:** Neon PostgreSQL (`user_data` table)"
    )

    # Render interactive multi-turn chat window component
    gr.ChatInterface(
        fn=chat_with_agent,
        examples=test_examples,
        cache_examples=False,  # Disable static cache to force dynamic live server integration
    )

if __name__ == "__main__":
    demo.launch(
        theme=gr.themes.Soft()
    )  # Moved theme configuration here to support Gradio 6.0+
