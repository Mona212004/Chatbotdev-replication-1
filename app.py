import os
import sys
import asyncio
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

# 1. Import official Google ADK execution components
from google.adk import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types

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

        # 3. Create the execution runner pointing to your root agent brain
        runner = Runner(
            app_name="movie_rec_app",
            agent=root_agent,
            session_service=session_service,
        )

        # 4. Package the incoming plain-text message into the required GenAI Content structure
        content = types.Content(role="user", parts=[types.Part(text=user_message)])

        # 5. Run the agent asynchronously over the persistent session thread
        events_async = runner.run_async(
            session_id=GLOBAL_SESSION_ID,
            user_id="default_web_user",
            new_message=content,
        )

        # 6. Consume the asynchronous event stream and stitch together the text blocks
        response_text = ""
        async for event in events_async:
            if event.content and event.content.parts:
                for part in event.content.parts:
                    if part.text:
                        response_text += part.text

        return {"response": response_text.strip()}

    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})


# Render Container Binding
if __name__ == "__main__":
    import uvicorn

    port = int(os.getenv("PORT", 10000))
    uvicorn.run(app, host="0.0.0.0", port=port)
