import os
import sys
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from movieRec.movieRecommendation2.agent import root_agent

app = FastAPI(title="AI Movie Recommender API")


@app.post("/chat")
async def chat(request: Request):
    try:
        data = await request.json()
        user_message = data.get("message")

        if not user_message:
            return JSONResponse(
                status_code=400, content={"error": "Message parameter is required"}
            )

        # Invokes your agent logic exactly like your local environment does
        response = root_agent.run(user_message)
        return {"response": response}

    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})


# Render requirements: The container must dynamically bind to the $PORT assigned by the platform
if __name__ == "__main__":
    import uvicorn

    # Render automatically injects a "PORT" variable. We default to 10000 if it's missing.
    port = int(os.getenv("PORT", 10000))
    uvicorn.run(app, host="0.0.0.0", port=port)
