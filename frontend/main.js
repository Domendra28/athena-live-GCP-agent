/**
 * Athena Live Voice Assistant — Client Logic
 */

let socket = null;
let audioCtx = null;
let micStream = null;
let workletNode = null;
let isConnected = false;
let isRecording = false;
let isSpeaking = false;
let isMuted = false;
let messageCount = 0;

const BARGE_RMS_THRESHOLD = 0.025; // Client-side instant barge-in

// Streaming transcript state
let currentBubble = null;
let currentRole = null;
let transcriptResetTimer = null;

// Audio playback queue (24kHz PCM from Gemini Live)
let nextPlayTime = 0;
let activeAudioSources = [];

// DOM Elements
const statusDot = document.getElementById('status-dot');
const statusText = document.getElementById('status-text');
const latencyText = document.getElementById('latency-text');
const orbRing = document.getElementById('orb-ring');
const orbCore = document.getElementById('orb-core');
const voiceStatePill = document.getElementById('voice-state-pill');
const voiceStateLabel = document.getElementById('voice-state-label');
const micToggleBtn = document.getElementById('mic-toggle-btn');
const muteBtn = document.getElementById('mute-btn');
const hangupBtn = document.getElementById('hangup-btn');
const clearChatBtn = document.getElementById('clear-chat-btn');
const transcriptContainer = document.getElementById('transcript-container');
const visualContainer = document.getElementById('visual-container');
const messageCountLabel = document.getElementById('message-count');
const waveformCanvas = document.getElementById('waveform-canvas');
const canvasCtx = waveformCanvas.getContext('2d');

let analyser = null;
let animationFrameId = null;

// Initialize Waveform Canvas
function drawWaveform() {
    animationFrameId = requestAnimationFrame(drawWaveform);

    const width = waveformCanvas.width;
    const height = waveformCanvas.height;
    canvasCtx.clearRect(0, 0, width, height);

    if (!analyser || !isRecording) {
        canvasCtx.beginPath();
        canvasCtx.strokeStyle = '#e2e8f0';
        canvasCtx.lineWidth = 2;
        canvasCtx.moveTo(0, height / 2);
        canvasCtx.lineTo(width, height / 2);
        canvasCtx.stroke();
        return;
    }

    const bufferLength = analyser.frequencyBinCount;
    const dataArray = new Uint8Array(bufferLength);
    analyser.getByteTimeDomainData(dataArray);

    const gradient = canvasCtx.createLinearGradient(0, 0, width, 0);
    gradient.addColorStop(0, '#6366f1');
    gradient.addColorStop(0.5, '#a855f7');
    gradient.addColorStop(1, '#ec4899');

    canvasCtx.lineWidth = 2.5;
    canvasCtx.strokeStyle = gradient;
    canvasCtx.beginPath();

    const sliceWidth = width / bufferLength;
    let x = 0;

    for (let i = 0; i < bufferLength; i++) {
        const v = dataArray[i] / 128.0;
        const y = (v * height) / 2;

        if (i === 0) {
            canvasCtx.moveTo(x, y);
        } else {
            canvasCtx.lineTo(x, y);
        }
        x += sliceWidth;
    }

    canvasCtx.lineTo(width, height / 2);
    canvasCtx.stroke();
}

drawWaveform();

// Toggle Session Start / Stop
micToggleBtn.addEventListener('click', async () => {
    if (!isConnected) {
        await startSession();
    } else {
        stopSession();
    }
});

hangupBtn.addEventListener('click', () => {
    if (isConnected) stopSession();
});

muteBtn.addEventListener('click', () => {
    isMuted = !isMuted;
    muteBtn.classList.toggle('text-red-500', isMuted);
    muteBtn.title = isMuted ? "Unmute Athena Voice" : "Mute Athena Voice";
});

clearChatBtn.addEventListener('click', () => {
    transcriptContainer.innerHTML = `
        <div id="empty-transcript-hint" class="text-center py-8 text-slate-400 text-xs">
            <i data-lucide="mic" class="w-6 h-6 mx-auto mb-2 opacity-50"></i>
            Transcript cleared.
        </div>
    `;
    messageCount = 0;
    messageCountLabel.textContent = "0 messages";
    currentBubble = null;
    currentRole = null;
    lucide.createIcons();
});

// Start Live WebSocket & Audio Session
async function startSession() {
    updateStatus('connecting', 'Connecting...');
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${protocol}//${window.location.host}/ws`;

    try {
        socket = new WebSocket(wsUrl);
        socket.binaryType = 'arraybuffer';

        socket.onopen = async () => {
            isConnected = true;
            updateStatus('connected', 'Athena Connected');
            await initAudio();
        };

        socket.onmessage = (event) => {
            if (typeof event.data === 'string') {
                const msg = JSON.parse(event.data);
                handleServerMessage(msg);
            } else if (event.data instanceof ArrayBuffer) {
                // Incoming 24kHz PCM synthesized speech
                playPcmAudio(event.data);
            }
        };

        socket.onclose = () => {
            stopSession();
        };

        socket.onerror = (err) => {
            console.error('WebSocket Error:', err);
            updateStatus('error', 'Connection Error');
            stopSession();
        };

    } catch (err) {
        console.error('Failed to connect:', err);
        updateStatus('error', 'Failed to connect');
    }
}

// Initialize Microphone and AudioContext
async function initAudio() {
    try {
        audioCtx = new (window.AudioContext || window.webkitAudioContext)();
        if (audioCtx.state === 'suspended') {
            await audioCtx.resume();
        }

        await audioCtx.audioWorklet.addModule('pcm-processor.js');

        micStream = await navigator.mediaDevices.getUserMedia({
            audio: {
                channelCount: 1,
                echoCancellation: true,
                noiseSuppression: true,
                autoGainControl: true
            }
        });

        const micSource = audioCtx.createMediaStreamSource(micStream);
        analyser = audioCtx.createAnalyser();
        analyser.fftSize = 256;
        micSource.connect(analyser);

        workletNode = new AudioWorkletNode(audioCtx, 'pcm-processor');
        workletNode.port.onmessage = (event) => {
            const { pcm, rms } = event.data;
            if (socket && socket.readyState === WebSocket.OPEN && pcm) {
                socket.send(pcm); // Stream 16kHz PCM bytes to server immediately
            }
            // Client-side Instant Barge-in
            if (rms >= BARGE_RMS_THRESHOLD && isSpeaking) {
                stopAllAudioPlayback();
            }
        };

        micSource.connect(workletNode);
        workletNode.connect(audioCtx.destination); // Keep audio graph alive

        isRecording = true;
        setVoiceState('listening', 'Athena is Listening...');

    } catch (err) {
        console.error('Microphone Error:', err);
        alert('Microphone access denied or audio worklet failed.');
        stopSession();
    }
}

// Stop Live Session
function stopSession() {
    isConnected = false;
    isRecording = false;
    isSpeaking = false;
    currentBubble = null;
    currentRole = null;

    if (workletNode) { workletNode.disconnect(); workletNode = null; }
    if (micStream) { micStream.getTracks().forEach(t => t.stop()); micStream = null; }
    if (socket && socket.readyState === WebSocket.OPEN) { socket.close(); }
    if (audioCtx) { audioCtx.close(); audioCtx = null; }

    stopAllAudioPlayback();
    updateStatus('offline', 'Ready to Connect');
    setVoiceState('offline', 'Microphone Offline');
}

// Play 24kHz Raw PCM Audio from Gemini Live with minimum jitter
function playPcmAudio(arrayBuffer) {
    if (isMuted || !audioCtx) return;

    isSpeaking = true;
    setVoiceState('speaking', 'Athena is Speaking...');

    const int16Array = new Int16Array(arrayBuffer);
    const float32Array = new Float32Array(int16Array.length);

    for (let i = 0; i < int16Array.length; i++) {
        float32Array[i] = int16Array[i] / 0x8000;
    }

    const audioBuffer = audioCtx.createBuffer(1, float32Array.length, 24000);
    audioBuffer.getChannelData(0).set(float32Array);

    const source = audioCtx.createBufferSource();
    source.buffer = audioBuffer;
    source.connect(audioCtx.destination);

    const now = audioCtx.currentTime;
    if (nextPlayTime < now) {
        nextPlayTime = now + 0.01; // Tiny 10ms jitter buffer
    }

    source.start(nextPlayTime);
    nextPlayTime += audioBuffer.duration;

    activeAudioSources.push(source);
    source.onended = () => {
        const idx = activeAudioSources.indexOf(source);
        if (idx !== -1) activeAudioSources.splice(idx, 1);
        if (activeAudioSources.length === 0 && isRecording) {
            isSpeaking = false;
            setVoiceState('listening', 'Athena is Listening...');
        }
    };
}

// Stop all playing audio instantly when interrupted (Barge-in)
function stopAllAudioPlayback() {
    for (const source of activeAudioSources) {
        try { source.stop(); } catch (e) {}
    }
    activeAudioSources = [];
    nextPlayTime = 0;
    isSpeaking = false;
    currentBubble = null;
    currentRole = null;
    if (isRecording) {
        setVoiceState('listening', 'Athena is Listening...');
    }
}

// Handle incoming JSON events from server
function handleServerMessage(msg) {
    if (msg.type === 'transcript') {
        appendStreamingTranscript(msg.role, msg.text);
    } else if (msg.type === 'interrupted') {
        console.log('⚡ Interrupted / Barge-in');
        stopAllAudioPlayback();
    } else if (msg.type === 'tool_action') {
        renderToolVisual(msg.action, msg.data);
    }
}

// Append or Stream Transcripts with preserved spacing and word integrity
function appendStreamingTranscript(role, rawText) {
    if (!rawText) return;

    const hint = document.getElementById('empty-transcript-hint');
    if (hint) hint.remove();

    // If same speaker within active turn, append chunk directly (keeping Gemini's exact spacing)
    if (currentBubble && currentRole === role) {
        const p = currentBubble.querySelector('p');
        if (p) {
            // Check if rawText already starts with space or current text ends with space
            const current = p.textContent;
            if (current.endsWith(rawText.trim()) && current.length > 30) {
                // Avoid rare whole-turn duplicate echo from end-of-turn events
                return;
            }
            p.textContent += rawText;
        }
    } else {
        // New speaker turn -> create a fresh bubble
        currentRole = role;
        messageCount++;
        messageCountLabel.textContent = `${messageCount} message${messageCount > 1 ? 's' : ''}`;

        const isUser = role === 'user';
        const bubble = document.createElement('div');
        bubble.className = `p-3 rounded-2xl text-xs leading-relaxed max-w-[92%] shadow-sm transition-all ${
            isUser
                ? 'ml-auto bg-indigo-600 text-white rounded-tr-sm'
                : 'mr-auto bg-white border border-slate-200 text-slate-800 rounded-tl-sm'
        }`;

        const time = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });

        bubble.innerHTML = `
            <div class="flex items-center justify-between mb-1 opacity-75 font-semibold text-[10px]">
                <span>${isUser ? 'You' : 'Athena'}</span>
                <span>${time}</span>
            </div>
            <p class="whitespace-pre-wrap">${rawText}</p>
        `;

        transcriptContainer.appendChild(bubble);
        currentBubble = bubble;
    }

    transcriptContainer.scrollTop = transcriptContainer.scrollHeight;

    // Reset current bubble reference after 4 seconds of silence so next utterance starts a fresh bubble
    if (transcriptResetTimer) clearTimeout(transcriptResetTimer);
    transcriptResetTimer = setTimeout(() => {
        currentBubble = null;
        currentRole = null;
    }, 4000);
}

// Render Visuals & Links in Right Column
function renderToolVisual(action, data) {
    const card = document.createElement('div');
    card.className = 'p-4 rounded-xl bg-white border border-slate-200 shadow-sm space-y-3 transition-all hover:shadow-md';

    if (action === 'render_visual') {
        let diagramHtml = '';
        if (data.diagram) {
            diagramHtml = `
                <div class="p-3 bg-slate-50 rounded-lg overflow-x-auto text-xs font-mono text-slate-700">
                    <pre class="mermaid">${data.diagram}</pre>
                </div>
            `;
        }

        let keyPointsHtml = '';
        if (data.key_points && data.key_points.length > 0) {
            keyPointsHtml = `
                <ul class="text-xs space-y-1 text-slate-600">
                    ${data.key_points.map(pt => `<li class="flex items-center gap-1.5"><i data-lucide="check" class="w-3.5 h-3.5 text-emerald-500 flex-shrink-0"></i><span>${pt}</span></li>`).join('')}
                </ul>
            `;
        }

        card.innerHTML = `
            <div class="flex items-center justify-between">
                <span class="text-[10px] font-bold tracking-wider uppercase text-purple-600 bg-purple-50 px-2 py-0.5 rounded">${data.visual_type || 'Diagram'}</span>
                <i data-lucide="image" class="w-4 h-4 text-purple-500"></i>
            </div>
            <h4 class="font-bold text-slate-800 text-sm">${data.title}</h4>
            <p class="text-xs text-slate-600">${data.caption}</p>
            ${diagramHtml}
            ${keyPointsHtml}
        `;

    } else if (action === 'show_link_card') {
        card.innerHTML = `
            <div class="flex items-center justify-between">
                <span class="text-[10px] font-bold tracking-wider uppercase text-blue-600 bg-blue-50 px-2 py-0.5 rounded">Resource Link</span>
                <i data-lucide="external-link" class="w-4 h-4 text-blue-500"></i>
            </div>
            <h4 class="font-bold text-slate-800 text-sm">${data.title}</h4>
            <p class="text-xs text-slate-600">${data.description || 'Reference documentation & guide.'}</p>
            <a href="${data.url}" target="_blank" rel="noopener noreferrer" class="mt-2 inline-flex items-center justify-between w-full px-3 py-2 text-xs font-medium text-indigo-600 bg-indigo-50/80 rounded-lg hover:bg-indigo-100 transition">
                <span class="truncate">${data.url}</span>
                <i data-lucide="arrow-up-right" class="w-4 h-4 flex-shrink-0 ml-1"></i>
            </a>
        `;

    } else if (action === 'show_gcp_card') {
        card.innerHTML = `
            <div class="flex items-center justify-between">
                <span class="text-[10px] font-bold tracking-wider uppercase text-amber-600 bg-amber-50 px-2 py-0.5 rounded">Google Cloud</span>
                <i data-lucide="cloud" class="w-4 h-4 text-amber-500"></i>
            </div>
            <h4 class="font-bold text-slate-800 text-sm">${data.service || 'GCP Resource'}</h4>
            <p class="text-xs text-slate-600 font-medium">${data.summary}</p>
            <div class="p-2.5 bg-slate-50 rounded-lg text-xs text-slate-700">
                ${data.details || 'Live GCP service context active.'}
            </div>
        `;

    } else if (action === 'show_learning_widget') {
        card.innerHTML = `
            <div class="flex items-center justify-between">
                <span class="text-[10px] font-bold tracking-wider uppercase text-emerald-600 bg-emerald-50 px-2 py-0.5 rounded">Learning Module</span>
                <i data-lucide="book-open" class="w-4 h-4 text-emerald-500"></i>
            </div>
            <h4 class="font-bold text-slate-800 text-sm">${data.topic}</h4>
            <p class="text-xs text-slate-600">Action: <span class="font-semibold text-slate-700">${data.action}</span> (${data.difficulty || 'intermediate'})</p>
            <div class="p-2.5 bg-emerald-50/60 border border-emerald-100 rounded-lg text-xs text-emerald-800">
                ${data.result || 'Learning session in progress.'}
            </div>
        `;
    }

    visualContainer.prepend(card);
    lucide.createIcons();
    try { mermaid.init(undefined, card.querySelectorAll('.mermaid')); } catch (e) {}
}

// Status Updates
function updateStatus(state, label) {
    if (state === 'connected') {
        statusDot.className = 'w-2.5 h-2.5 rounded-full bg-emerald-500';
        statusText.textContent = label;
        latencyText.textContent = '14ms';
        micToggleBtn.className = 'w-14 h-14 rounded-full bg-gradient-to-r from-red-500 to-pink-600 text-white shadow-glow hover:scale-105 active:scale-95 transition-all flex items-center justify-center focus:outline-none';
        micToggleBtn.innerHTML = '<i data-lucide="square" class="w-6 h-6"></i>';
    } else if (state === 'connecting') {
        statusDot.className = 'w-2.5 h-2.5 rounded-full bg-amber-400 animate-pulse';
        statusText.textContent = label;
        latencyText.textContent = '-- ms';
    } else {
        statusDot.className = 'w-2.5 h-2.5 rounded-full bg-slate-300';
        statusText.textContent = label;
        latencyText.textContent = '-- ms';
        micToggleBtn.className = 'w-14 h-14 rounded-full bg-gradient-to-r from-indigo-500 to-purple-600 text-white shadow-glow hover:scale-105 active:scale-95 transition-all flex items-center justify-center focus:outline-none';
        micToggleBtn.innerHTML = '<i data-lucide="mic" class="w-6 h-6"></i>';
    }
    lucide.createIcons();
}

function setVoiceState(state, label) {
    if (state === 'speaking') {
        orbRing.className = 'w-44 h-44 rounded-full bg-gradient-to-tr from-indigo-400/20 via-purple-400/25 to-pink-400/20 flex items-center justify-center orb-speaking transition-all duration-300';
        voiceStatePill.className = 'mt-4 px-4 py-1.5 rounded-full bg-purple-50 shadow-sm border border-purple-200 text-xs font-semibold text-purple-700 flex items-center gap-2';
        voiceStateLabel.textContent = label;
    } else if (state === 'listening') {
        orbRing.className = 'w-44 h-44 rounded-full bg-gradient-to-tr from-indigo-400/20 via-purple-400/25 to-pink-400/20 flex items-center justify-center transition-all duration-300';
        voiceStatePill.className = 'mt-4 px-4 py-1.5 rounded-full bg-emerald-50 shadow-sm border border-emerald-200 text-xs font-semibold text-emerald-700 flex items-center gap-2';
        voiceStateLabel.textContent = label;
    } else {
        orbRing.className = 'w-44 h-44 rounded-full bg-gradient-to-tr from-indigo-400/20 via-purple-400/25 to-pink-400/20 flex items-center justify-center transition-all duration-300';
        voiceStatePill.className = 'mt-4 px-4 py-1.5 rounded-full bg-white shadow-sm border border-slate-200 text-xs font-semibold text-slate-700 flex items-center gap-2';
        voiceStateLabel.textContent = label;
    }
}
