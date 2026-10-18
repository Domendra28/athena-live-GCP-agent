"""Athena Agent Definition."""

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[1] / ".env")

from google.adk.agents import Agent
from google.adk.models import Gemini
from google.genai import types

from .persona import ATHENA_INSTRUCTION
from .tools import display_visual, gcp_assistant, learning_assistant, send_resource_link
from .browser_tools import (
    browser_open, browser_inspect, browser_search,
    browser_click, browser_type, browser_scroll, browser_close
)

VOICE_NAME = os.getenv("LIVE_VOICE", "Aoede")
MODEL_NAME = os.getenv("LIVE_MODEL", "gemini-3.8-live")

root_agent = Agent(
    model=Gemini(
        model=MODEL_NAME,
        speech_config=types.SpeechConfig(
            voice_config=types.VoiceConfig(
                prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name=VOICE_NAME)
            )
        ),
    ),
    name="athena",
    instruction=ATHENA_INSTRUCTION,
    tools=[
        gcp_assistant, learning_assistant, display_visual, send_resource_link,
        browser_open, browser_inspect, browser_search,
        browser_click, browser_type, browser_scroll, browser_close
    ],
)
