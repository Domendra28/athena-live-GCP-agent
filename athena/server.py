"""Athena Live Voice Server with Google ADK."""
import asyncio
import json
import logging
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[1] / ".env")

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from google.genai import types
from google.adk.runners import Runner, RunConfig
from google.adk.agents.run_config import StreamingMode
from google.adk.agents import LiveRequestQueue
from google.adk.sessions import InMemorySessionService

from .agent import root_agent
from .tools import to_frontend_action

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("athena-live")

VOICE = os.getenv("LIVE_VOICE", "Aoede")
APP_NAME = "athena-voice-assistant"

session_service = InMemorySessionService()
runner = Runner(app_name=APP_NAME, agent=root_agent, session_service=session_service)

RUN_CONFIG = RunConfig(
    streaming_mode=StreamingMode.BIDI,
    response_modalities=["AUDIO"],
    speech_config=types.SpeechConfig(
        voice_config=types.VoiceConfig(
            prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name=VOICE)
        )
    ),
    input_audio_transcription=types.AudioTranscriptionConfig(),
    output_audio_transcription=types.AudioTranscriptionConfig(),
)

app = FastAPI(title="Athena Voice Assistant")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

FRONTEND = Path(__file__).resolve().parents[1] / "frontend"


@app.websocket("/ws")
async def ws_endpoint(websocket: WebSocket):
    await websocket.accept()
    log.info("WebSocket connected. Starting live session for Athena.")
    
    session = await session_service.create_session(app_name=APP_NAME, user_id="user_listener")
    live_request_queue = LiveRequestQueue()

    async def upstream():
        """Receive 16kHz PCM audio bytes from microphone and feed into LiveRequestQueue."""
        while True:
            msg = await websocket.receive()
            if msg.get("type") == "websocket.disconnect":
                log.info("Client disconnected.")
                return
            
            raw_bytes = msg.get("bytes")
            if raw_bytes:
                live_request_queue.send_realtime(
                    types.Blob(data=raw_bytes, mime_type="audio/pcm;rate=16000")
                )

    async def handle_event(event):
        """Process Gemini Live events: audio chunks, transcripts, tool actions, and barge-in."""
        # 1. User spoken transcript
        it = getattr(event, "input_transcription", None)
        if it and getattr(it, "text", None):
            await websocket.send_text(json.dumps({"type": "transcript", "role": "user", "text": it.text}))

        # 2. Athena spoken transcript
        ot = getattr(event, "output_transcription", None)
        if ot and getattr(ot, "text", None):
            await websocket.send_text(json.dumps({"type": "transcript", "role": "athena", "text": ot.text}))

        # 3. Audio bytes & tool calls
        content = getattr(event, "content", None)
        if content and getattr(content, "parts", None):
            for part in content.parts:
                # 24kHz synthesized audio
                inline_data = getattr(part, "inline_data", None)
                if inline_data and getattr(inline_data, "data", None):
                    await websocket.send_bytes(inline_data.data)

                # Tool executions -> Frontend Visual Cards / Links
                fc = getattr(part, "function_call", None)
                if fc:
                    action_cmd = to_frontend_action(fc.name, dict(getattr(fc, "args", None) or {}))
                    if action_cmd:
                        await websocket.send_text(json.dumps({"type": "tool_action", **action_cmd}))

        # 4. Interruption (User barged in while Athena was speaking)
        if getattr(event, "interrupted", None):
            await websocket.send_text(json.dumps({"type": "interrupted"}))

    async def downstream():
        """Continuously receive live responses from ADK runner."""
        async for event in runner.run_live(
            user_id=session.user_id,
            session_id=session.id,
            live_request_queue=live_request_queue,
            run_config=RUN_CONFIG,
        ):
            await handle_event(event)

    up_task = asyncio.create_task(upstream(), name="upstream")
    down_task = asyncio.create_task(downstream(), name="downstream")

    try:
        done, pending = await asyncio.wait({up_task, down_task}, return_when=asyncio.FIRST_COMPLETED)
        live_request_queue.close()
        for t in done:
            exc = t.exception()
            if exc:
                log.exception("%s failed: %r", t.get_name(), exc)
                try:
                    await websocket.send_text(json.dumps({"type": "error", "message": str(exc)}))
                except Exception:
                    pass
        for t in pending:
            t.cancel()
        await asyncio.gather(*pending, return_exceptions=True)
    except WebSocketDisconnect:
        log.info("WebSocket disconnected.")
    finally:
        live_request_queue.close()


if FRONTEND.exists():
    app.mount("/", StaticFiles(directory=str(FRONTEND), html=True), name="frontend")
