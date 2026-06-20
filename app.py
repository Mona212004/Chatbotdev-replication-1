import os
import sys
import asyncio
import re  # Added for thought-tag filtering
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

# 1. Import official Google ADK execution components
from google.adk import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types

# --- BULLETPROOF FIX: Monkeypatch LiteLLM to strip reasoning_content from history ---
import litellm

orig_acompletion = litellm.acompletion
orig_completion = litellm.completion


def clean_messages(messages):
    if isinstance(messages, list):
        for msg in messages:
            # Handle standard dictionary items
            if isinstance(msg, dict):
                msg.pop("reasoning_content", None)
                if "message" in msg and isinstance(msg["message"], dict):
                    msg["message"].pop("reasoning_content", None)
            # Handle structured objects or Pydantic models safely
            else:
                if hasattr(msg, "reasoning_content"):
                    try:
                        delattr(msg, "reasoning_content")
                    except Exception:
                        try:
                            setattr(msg, "reasoning_content", None)
                        except Exception:
                            pass
                if hasattr(msg, "message"):
                    inner = getattr(msg, "message", None)
                    if isinstance(inner, dict):
                        inner.pop("reasoning_content", None)
                    elif inner and hasattr(inner, "reasoning_content"):
                        try:
                            delattr(inner, "reasoning_content")
                        except Exception:
                            try:
                                setattr(inner, "reasoning_content", None)
                            except Exception:
                                pass
    return messages


async def patched_acompletion(*args, **kwargs):
    if "messages" in kwargs:
        kwargs["messages"] = clean_messages(kwargs["messages"])
    return await orig_acompletion(*args, **kwargs)


def patched_completion(*args, **kwargs):
    if "messages" in kwargs:
        kwargs["messages"] = clean_messages(kwargs["messages"])
    return orig_completion(*args, **kwargs)


litellm.acompletion = patched_acompletion
litellm.completion = patched_completion
# ----------------------------------------------------------------------------------

# Import your configured root agent
from movieRec.movieRecommendation2.agent import root_agent

app = FastAPI(title="AI Movie Recommender API")

# 2. Initialize a global Session Service so chat history persists between HTTP requests
session_service = InMemorySessionService()
GLOBAL_SESSION_ID = "movie_recommender_web_session"


@app.on_event("startup")
async def startup_event():
    """Pre-create a stable, continuous session thread on application startup."""
    await session_service.create_session(
        session_id=GLOBAL_SESSION_ID,
        state={},
        app_name="movie_rec_app",
        user_id="default_web_user",
    )


@app.post("/chat")
async def chat(request: Request):
    try:
        data = await request.json()
        user_message = data.get("message")

        if not user_message:
            return JSONResponse(
                status_code=400, content={"error": "Message parameter is required"}
            )

        # Create the execution runner pointing to your root agent brain
        runner = Runner(
            app_name="movie_rec_app",
            agent=root_agent,
            session_service=session_service,
        )

        # Package the incoming plain-text message into the required GenAI Content structure
        content = types.Content(role="user", parts=[types.Part(text=user_message)])

        # Run the agent asynchronously over the persistent session thread
        events_async = runner.run_async(
            session_id=GLOBAL_SESSION_ID,
            user_id="default_web_user",
            new_message=content,
        )

        # Consume the asynchronous event stream and stitch together the text blocks
        response_text = ""
        async for event in events_async:
            if event.content and event.content.parts:
                for part in event.content.parts:
                    if part.text:
                        response_text += part.text

        # --- STREAM CLEANUP FIX: Strip out any raw thinking blocks or monologue text ---
        # Removes hidden or explicit <think> tokens along with any internal step logic text block
        response_text = re.sub(
            r"<think>.*?</think>", "", response_text, flags=re.DOTALL
        )
        response_text = re.sub(
            r"(The user is introducing themselves|According to the instructions|I will call sayHello).*?(\n|$)",
            "",
            response_text,
        )
        # -------------------------------------------------------------------------------

        return {"response": response_text.strip()}

    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})


# Render Container Binding
if __name__ == "__main__":
    import uvicorn

    port = int(os.getenv("PORT", 10000))
    uvicorn.run(app, host="0.0.0.0", port=port)
