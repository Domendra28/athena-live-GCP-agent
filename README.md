# ⚡ Athena — Multimodal Live Voice Assistant
Athena is an interactive, full-duplex **Live Voice AI Assistant** powered by the **Gemini Multimodal Live API** and **Google ADK** (Agent Development Kit). 
Unlike standard text-chatbots or turn-based voice bots, Athena communicates through low-latency bidirectional audio streaming. You can speak to her naturally, talk over her mid-sentence (**barge-in interruption**), and see real-time visual diagrams and clickable resource link cards pop up on your screen while she talks.
---
## ✨ Key Features
- **🎙️ Full-Duplex Audio Streaming:** Real-time 16kHz microphone audio streaming up and 24kHz synthesized voice audio (`Aoede`) streaming down.
- **⚡ Native Barge-in / Interruption:** Interrupt Athena at any moment mid-sentence. Client and server detect speech instantly and cut off output audio buffers.
- **🖼️ Pictorial Diagrams & Visual Canvas (`display_visual`):** Renders flowcharts, architecture diagrams (Mermaid.js), and visual summary cards on screen when requested.
- **🔗 Clickable Link Sharing (`send_resource_link`):** Sends clean, clickable documentation links to the chat panel instead of reading out raw URLs.
- **☁️ Google Cloud Assistant (`gcp_assistant`):** Real-time GCP technical documentation, pricing overview, and architecture guidance.
- **📚 Socratic Learning Tutor (`learning_assistant`):** Interactive learning module for quizzing, topic breakdowns, and concept reviews.
- **🎨 Modern Light-Theme UI:** 3-column responsive layout built with Tailwind CSS, Lucide Icons, and HTML5 Web Audio Visualizer.
---
## 🛠️ Architecture Overview
```text
┌──────────────────────┐   WebSocket (Full-Duplex)   ┌────────────────────────┐
│  Browser Frontend    │ <─────────────────────────> │ FastAPI Backend (ADK)  │
│  - 16kHz Mic Input   │                             │ - LiveRequestQueue     │
│  - 24kHz Audio Play  │                             │ - ADK Runner           │
│  - Visual Canvas UI  │                             └───────────┬────────────┘
└──────────────────────┘                                         │ gRPC / Stream
                                                                 ▼
                                                    ┌────────────────────────┐
                                                    │  Gemini Live API       │
                                                    │  (gemini-2.0-flash-exp)│
                                                    └────────────────────────┘
```
---
## 📁 Project Structure


```text
athena_project/
├── athena/
│   ├── __init__.py         # Package initialization
│   ├── agent.py            # ADK Agent definition & model configuration
│   ├── persona.py          # Athena system instructions & persona prompt
│   ├── tools.py            # Custom tool functions (GCP, Learning, Visuals, Links)
│   └── server.py           # FastAPI server & WebSocket live streaming bridge
│
├── frontend/
│   ├── index.html          # Light-theme 3-column UI dashboard
│   ├── main.js             # Web Audio API, WebSocket client, barge-in logic
│   └── pcm-processor.js    # AudioWorklet downsampling mic audio to 16kHz PCM
│
├── .env.example            # Environment variables template
├── .gitignore              # Protects .env and sensitive credentials
├── pyproject.toml          # Project dependencies & package configuration
└── README.md               # Documentation
```
---
## 🚀 Quick Start
### 1. Prerequisites
- Python `>= 3.11`
- A **Google Gemini API Key** (from [Google AI Studio](https://aistudio.google.com/))
### 2. Installation
Clone the repository and navigate into the directory:
```bash
git clone https://github.com/YOUR_USERNAME/athena-live.git
cd athena-live
```
Install dependencies:
```bash
pip install fastapi "uvicorn[standard]" google-genai google-adk python-dotenv websockets
```

### 3. Environment Configuration
Copy `.env.example` to `.env`:
```bash
cp .env.example .env
```
Edit `.env` and paste your Gemini API key:
```env
GOOGLE_GENAI_USE_VERTEXAI=FALSE
GOOGLE_API_KEY=your_gemini_api_key_here
LIVE_MODEL=gemini-2.0-flash-exp
LIVE_VOICE=Aoede
OTEL_SDK_DISABLED=true
```
---
## 🖥️ Running the Application
### Option A: Custom FastAPI Server (Recommended)
Start the FastAPI server with Uvicorn:
```bash
uvicorn athena.server:app --port 8000
```
Open your browser at **[http://localhost:8000](http://localhost:8000)** and tap the microphone button to talk with Athena.
### Option B: ADK Web UI Preview
You can also run Athena inside Google ADK's built-in developer interface:
```bash
adk web . --port 8000
```
