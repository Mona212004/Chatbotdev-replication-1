import os
import sys
import asyncio
import re
import json
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

# 1. Import official Google ADK execution components
from google.adk import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types

# --- BULLETPROOF FIX: Monkeypatch LiteLLM to strip reasoning_content and fix tool array schemas ---
import litellm

orig_acompletion = litellm.acompletion
orig_completion = litellm.completion


def fix_json_arguments(args_str):
    """Safely converts string arguments into list arrays if a model misformats them."""
    if not args_str or not isinstance(args_str, str):
        return args_str
    try:
        data = json.loads(args_str)
        if isinstance(data, dict):
            # Enforce array types on array fields
            for field in ["movie_interests_titles", "liked_genres"]:
                if field in data and isinstance(data[field], str):
                    data[field] = [data[field]]
            return json.dumps(data)
    except Exception:
        pass
    return args_str


def patch_tools_schema(kwargs):
    """Bypasses local validation crashes by relaxing strict array constraints in the tool schema."""
    try:
        if "tools" in kwargs and isinstance(kwargs["tools"], list):
            for tool in kwargs["tools"]:
                if isinstance(tool, dict) and tool.get("type") == "function":
                    func = tool.get("function", {})
                    params = func.get("parameters", {})
                    properties = params.get("properties", {})
                    if isinstance(properties, dict):
                        for field in ["movie_interests_titles", "liked_genres"]:
                            if field in properties and isinstance(
                                properties[field], dict
                            ):
                                if properties[field].get("type") == "array":
                                    # Popping 'type' prevents validation errors if the model sends a string
                                    properties[field].pop("type", None)
    except Exception:
        pass


def fix_response_obj(response):
    """Normalizes tool arguments inside the response object before passing back to the runner."""
    if not response:
        return response
    try:
        if hasattr(response, "choices") and response.choices:
            for choice in response.choices:
                if hasattr(choice, "message") and choice.message:
                    msg = choice.message
                    if hasattr(msg, "tool_calls") and msg.tool_calls:
                        for tc in msg.tool_calls:
                            if hasattr(tc, "function") and tc.function:
                                if hasattr(tc.function, "arguments") and getattr(
                                    tc.function, "arguments"
                                ):
                                    setattr(
                                        tc.function,
                                        "arguments",
                                        fix_json_arguments(
                                            getattr(tc.function, "arguments")
                                        ),
                                    )
    except Exception:
        pass
    return response


def clean_messages(messages):
    if isinstance(messages, list):
        for msg in messages:
            # Handle standard dictionary items
            if isinstance(msg, dict):
                msg.pop("reasoning_content", None)
                if "message" in msg and isinstance(msg["message"], dict):
                    msg["message"].pop("reasoning_content", None)

                # Fix existing history tool calls if stored as dicts
                if "tool_calls" in msg and isinstance(msg["tool_calls"], list):
                    for tc in msg["tool_calls"]:
                        if (
                            isinstance(tc, dict)
                            and "function" in tc
                            and isinstance(tc["function"], dict)
                        ):
                            if "arguments" in tc["function"]:
                                tc["function"]["arguments"] = fix_json_arguments(
                                    tc["function"]["arguments"]
                                )
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

                if hasattr(msg, "tool_calls") and getattr(msg, "tool_calls"):
                    tcs = getattr(msg, "tool_calls")
                    if isinstance(tcs, list):
                        for tc in tcs:
                            if hasattr(tc, "function") and getattr(tc, "function"):
                                func = getattr(tc, "function")
                                if hasattr(func, "arguments") and getattr(
                                    func, "arguments"
                                ):
                                    try:
                                        setattr(
                                            func,
                                            "arguments",
                                            fix_json_arguments(
                                                getattr(func, "arguments")
                                            ),
                                        )
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
    patch_tools_schema(kwargs)
    res = await orig_acompletion(*args, **kwargs)
    return fix_response_obj(res)


def patched_completion(*args, **kwargs):
    if "messages" in kwargs:
        kwargs["messages"] = clean_messages(kwargs["messages"])
    patch_tools_schema(kwargs)
    res = orig_completion(*args, **kwargs)
    return fix_response_obj(res)


litellm.acompletion = patched_acompletion
litellm.completion = patched_completion
# ----------------------------------------------------------------------------------

# Import your configured root agent
from movieRec.movieRecommendation2.agent import root_agent

app = FastAPI(title="AI Movie Recommender API")

# 2. Initialize a global Session Service so chat history persists between HTTP requests
session_service = InMemorySessionService()
GLOBAL_SESSION_ID = "movie_recommender_web_session"

# Global singleton — Runner is expensive to instantiate; recreating it per request adds seconds of overhead
runner = None

# Token budget check: leaves headroom under Groq's 8000 TPM limit for the system
# prompt + tool schemas + new message overhead that isn't part of session.events.
TOKEN_BUDGET = 5000


@app.on_event("startup")
async def startup_event():
    global runner
    await session_service.create_session(
        session_id=GLOBAL_SESSION_ID,
        state={},
        app_name="movie_rec_app",
        user_id="default_web_user",
    )
    runner = Runner(
        app_name="movie_rec_app",
        agent=root_agent,
        session_service=session_service,
    )


def clean_agent_thinking(text: str) -> str:
    """Line-by-line filter to strip out raw text reasoning loops from the stream."""
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL)

    skip_patterns = [
        r"^username:.*",
        r"^user id:.*",
        r"^i will call.*",
        r"^i should not.*",
        r"^i will just.*",
        r"^let's check.*",
        r"^parameters:.*",
        r"^proceed.*",
        r"^wait, the prompt.*",
        r"^calling tool.*",
        r"^no other steps.*",
        r"^output matches.*",
        r"^done\b.*",
        r"^let's generate.*",
        r"^\[?self-correction.*",
        r"^check step.*",
        r"^step\s*\d+:.*",
        r"^matches exactly.*",
        r"^ready\b.*",
        r"^the user has successfully.*",
        r"^the tool output says:.*",
        r"^i need to relay.*",
        r"^no further action.*",
        r"^`?sayhello\(.*",
    ]

    lines = text.split("\n")
    filtered_lines = []

    for line in lines:
        trimmed = line.strip()
        if not trimmed:
            filtered_lines.append(line)
            continue

        should_skip = False
        for pattern in skip_patterns:
            if re.match(pattern, trimmed, re.IGNORECASE):
                should_skip = True
                break

        if not should_skip:
            filtered_lines.append(line)

    return "\n".join(filtered_lines).strip()


def estimate_tokens(events) -> int:
    """Rough token estimate across session events (~4 chars per token)."""
    total_chars = 0
    for e in events:
        if e.content and e.content.parts:
            for p in e.content.parts:
                if getattr(p, "text", None):
                    total_chars += len(p.text)
    return total_chars // 4


@app.post("/chat")
async def chat(request: Request):
    try:
        data = await request.json()
        user_message = data.get("message")

        if not user_message:
            return JSONResponse(
                status_code=400, content={"error": "Message parameter is required"}
            )

        content = types.Content(role="user", parts=[types.Part(text=user_message)])

        # Trim session history to stay within Groq's 8k TPM limit. Three-part strategy:
        # 1. Strip heavy content (recommendation lists, get_movie_info dumps, find_movie_title
        #    results) from older events — these are large but not needed for the agent to
        #    remember who the user is or what they like. Always keep AUTH_SUCCESS and
        #    preference confirmations intact, regardless of age, since the agent needs
        #    user_id/username/preferences for correct routing on every turn.
        # 2. Cap total events to the last 12 turns as a hard ceiling.
        # 3. Auto-reset: if the trimmed history is STILL over budget (e.g. a burst of
        #    back-to-back recommendation/search queries with no idle gap), wipe the
        #    conversational history entirely and keep only light (auth/preference)
        #    events. This is size-triggered, not time-triggered, so it fires exactly
        #    when needed instead of relying on the user waiting out the rate limit.
        HEAVY_MARKERS = [
            "Match Confidence",
            "Core Premise",
            "Plot Summary",
            "Plot Synopsis",
            "🎬",
            "Candidate #",
            "you're looking for is",
        ]
        LIGHT_MARKERS = [
            "AUTH_SUCCESS",
            "preferences for user ID",
            "preferences have been",
            "preferences are:",
            "removed",
        ]

        def _is_heavy(event) -> bool:
            if not (event.content and event.content.parts):
                return False
            for p in event.content.parts:
                if p.text and any(m in p.text for m in HEAVY_MARKERS):
                    return True
            return False

        def _is_light(event) -> bool:
            if not (event.content and event.content.parts):
                return False
            for p in event.content.parts:
                if p.text and any(m in p.text for m in LIGHT_MARKERS):
                    return True
            return False

        session = await session_service.get_session(
            app_name="movie_rec_app",
            user_id="default_web_user",
            session_id=GLOBAL_SESSION_ID,
        )
        if session and hasattr(session, "events") and len(session.events) > 12:
            light_events = [e for e in session.events if _is_light(e)]
            recent_events = session.events[-12:]
            # Drop heavy recommendation/search-result events from the recent window
            # too — they're large and not needed for the agent to keep context.
            recent_events = [e for e in recent_events if not _is_heavy(e)]
            # Always keep light (auth/preference) events even if older than the window
            for e in light_events:
                if e not in recent_events:
                    recent_events.insert(0, e)
            session.events = recent_events

        # Auto-reset safety net: fires regardless of elapsed time, only on actual size.
        if session and hasattr(session, "events"):
            if estimate_tokens(session.events) > TOKEN_BUDGET:
                session.events = [e for e in session.events if _is_light(e)]

        events_async = runner.run_async(
            session_id=GLOBAL_SESSION_ID,
            user_id="default_web_user",
            new_message=content,
        )

        response_text = ""
        tools_called = []
        async for event in events_async:
            # Collect tool names from all events (tool calls fire before the final response event)
            if event.content and event.content.parts:
                for part in event.content.parts:
                    fc = getattr(part, "function_call", None)
                    if fc and getattr(fc, "name", None):
                        tools_called.append(fc.name)

            # Only pull text from the final response — skips all intermediate tool call/result
            # events that previously required clean_agent_thinking to filter out
            if event.is_final_response() and event.content and event.content.parts:
                for part in event.content.parts:
                    if part.text:
                        response_text += part.text

        response_text = clean_agent_thinking(response_text)

        if tools_called:
            response_text = f"[Tool: {', '.join(tools_called)}]\n{response_text}"

        return {"response": response_text}

    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})


if __name__ == "__main__":
    import uvicorn

    port = int(os.getenv("PORT", 10000))
    uvicorn.run(app, host="0.0.0.0", port=port)
