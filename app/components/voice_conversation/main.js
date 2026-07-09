/**
 * Live voice check-in component.
 *
 * Runs entirely client-side: mic capture + resampling (emotion-worklet.js),
 * a direct browser-to-Gemini-Live WebSocket session, an agent-voice gate that
 * keeps the agent's own audio out of what gets collected, and in-memory
 * accumulation of the gated-in (user-only) PCM. When the conversation ends
 * (target speech collected, timeout, or manual wrap-up) the accumulated audio
 * is encoded into one WAV blob and handed to Python once, via the Streamlit
 * component value bridge. No real-time classification happens here or
 * anywhere in this feature — classification is a single batch call in
 * Python, on the full collected audio, via the existing (unmodified)
 * predict_zone_from_audio().
 *
 * The agent-voice gate technique (the part that must not fail) is ported
 * from the reference implementation's gemini.ts: the gate closes (mutes
 * further mic frames from being sent to Gemini or accumulated) the instant
 * Gemini's audio starts arriving, and only reopens once the *scheduled*
 * playback has actually finished (AudioBufferSourceNode.onended) — not
 * merely when the turnComplete message arrives, since audio is scheduled
 * into the future via a playHead pointer.
 */
(function () {
  'use strict';

  // ---------------------------------------------------------------------
  // Streamlit Components postMessage protocol (hand-rolled, no bundler).
  // Message type strings and payload shapes verified against the installed
  // Streamlit build (components/v1, CUSTOM_COMPONENT_API_VERSION = 1).
  // ---------------------------------------------------------------------
  function sendToStreamlit(type, data) {
    const payload = Object.assign({ isStreamlitMessage: true, type: type }, data);
    window.parent.postMessage(payload, '*');
  }
  function componentReady() {
    sendToStreamlit('streamlit:componentReady', { apiVersion: 1 });
  }
  function setFrameHeight(height) {
    sendToStreamlit('streamlit:setFrameHeight', { height: height });
  }
  function setComponentValue(value) {
    sendToStreamlit('streamlit:setComponentValue', { value: value, dataType: 'json' });
  }

  // ---------------------------------------------------------------------
  // DOM refs
  // ---------------------------------------------------------------------
  const els = {
    status: document.getElementById('status'),
    startBtn: document.getElementById('startBtn'),
    wrapUpBtn: document.getElementById('wrapUpBtn'),
    progressBar: document.getElementById('progressBar'),
    speechSeconds: document.getElementById('speechSeconds'),
    elapsedSeconds: document.getElementById('elapsedSeconds'),
    gateState: document.getElementById('gateState'),
  };

  // ---------------------------------------------------------------------
  // Config (populated from Streamlit args on each render)
  // ---------------------------------------------------------------------
  const CONFIG = {
    targetSpeechS: 50,
    timeoutS: 100,
    clientSecret: '',
    model: '',
    voice: '',
    wsUrl: '',
  };

  // ---------------------------------------------------------------------
  // Gemini Live wire constants
  // ---------------------------------------------------------------------
  const GEMINI_INPUT_MIME = 'audio/pcm;rate=16000';
  const PLAYBACK_RATE = 24000; // Gemini Live output PCM sample rate
  const WRAP_UP_MAX_WAIT_MS = 8000; // safety cap in case goodbye audio never signals onended

  const SYSTEM_INSTRUCTION =
    'You are the friendly check-in host inside EmoEating, an app that suggests meals ' +
    'matching how the user feels — read from the sound of their voice, never from their ' +
    'words. The user has just opened the app; this short chat is what personalizes it. ' +
    'Your goal: get them talking warmly and naturally for about a minute so the app can ' +
    'hear how they are doing. Open the conversation yourself: one brief, warm greeting ' +
    'plus one easy question about their day — do not wait for them to speak first. Then ' +
    'follow their lead, one short open question at a time: their day, their energy right ' +
    'now, what has been on their mind, or something they are looking forward to. Keep ' +
    'your own turns to one or two sentences; they should do most of the talking, so ' +
    'invite them to say more. Never discuss, suggest, or ask about food, meals, hunger, ' +
    'or nutrition — the app handles that after this chat. You are not a therapist and ' +
    'never diagnose. If they mention crisis or serious distress, acknowledge warmly, ' +
    'offer the 988 Suicide & Crisis Lifeline, and end gently. When told to wrap up, give ' +
    'one brief warm closing and stop talking.';

  // ---------------------------------------------------------------------
  // Conversation state
  // ---------------------------------------------------------------------
  const SR = 16000;
  const VAD_RMS_FLOOR = 50.0; // Int16 RMS floor — matches the reference implementation

  let audioCtxIn = null;
  let workletNode = null;
  let micStream = null;
  let audioCtxOut = null;
  let ws = null;
  let setupDone = false;
  let greetPending = false;
  let playHead = 0;
  let lastSource = null;

  let speaking = false; // agent-voice gate: true while agent audio is playing
  let started = false;
  let finished = false;
  let wrappingUp = false; // true once we've asked the agent to say goodbye
  let wrapUpTimeoutHandle = null;
  let startTimeMs = 0;
  let speechElapsedS = 0;
  let pcmChunks = []; // Int16Array[], gated-in (user-only) audio only
  let progressTimer = null;

  function setStatus(text) {
    if (els.status) els.status.textContent = text;
  }

  function b64encode(buf) {
    let bin = '';
    const bytes = new Uint8Array(buf);
    const chunkSize = 0x8000;
    for (let i = 0; i < bytes.length; i += chunkSize) {
      bin += String.fromCharCode.apply(null, bytes.subarray(i, i + chunkSize));
    }
    return btoa(bin);
  }
  function b64decode(s) {
    const bin = atob(s);
    const out = new Uint8Array(bin.length);
    for (let i = 0; i < bin.length; i++) out[i] = bin.charCodeAt(i);
    return out.buffer;
  }

  function computeFrameRms(int16Frame) {
    let sumSq = 0;
    for (let i = 0; i < int16Frame.length; i++) sumSq += int16Frame[i] * int16Frame[i];
    return Math.sqrt(sumSq / int16Frame.length);
  }

  // ---------------------------------------------------------------------
  // Mic frame handling: gated fan-out to (a) Gemini Live and (b) the local
  // SER accumulator. Both are gated by the same `speaking` flag, so the
  // agent never hears itself and its voice never reaches the accumulator.
  // ---------------------------------------------------------------------
  function onWorkletFrame(int16Frame) {
    if (!started || finished) return;
    if (speaking) return; // agent-voice gate

    if (ws && ws.readyState === WebSocket.OPEN && setupDone) {
      ws.send(
        JSON.stringify({
          realtimeInput: { audio: { data: b64encode(int16Frame.buffer), mimeType: GEMINI_INPUT_MIME } },
        })
      );
    }

    const rms = computeFrameRms(int16Frame);
    const frameDurationS = int16Frame.length / SR;
    if (rms >= VAD_RMS_FLOOR) {
      speechElapsedS += frameDurationS;
    }
    pcmChunks.push(int16Frame);
    maybeAutoWrapUp();
  }

  function updateProgressUI() {
    const elapsedS = (Date.now() - startTimeMs) / 1000;
    if (els.speechSeconds) els.speechSeconds.textContent = speechElapsedS.toFixed(0) + 's';
    if (els.elapsedSeconds) els.elapsedSeconds.textContent = elapsedS.toFixed(0) + 's';
    if (els.progressBar) {
      const pct = Math.min(100, (speechElapsedS / CONFIG.targetSpeechS) * 100);
      els.progressBar.style.width = pct + '%';
    }
    if (els.gateState) {
      els.gateState.textContent = !started
        ? 'Idle'
        : wrappingUp
          ? 'Wrapping up...'
          : speaking
            ? 'Agent is speaking...'
            : 'Listening to you...';
    }
  }

  function maybeAutoWrapUp() {
    if (wrappingUp) return;
    const elapsedS = (Date.now() - startTimeMs) / 1000;
    if (speechElapsedS >= CONFIG.targetSpeechS || elapsedS >= CONFIG.timeoutS) {
      wrapUp();
    }
  }

  // ---------------------------------------------------------------------
  // Gemini Live session
  // ---------------------------------------------------------------------
  function setupMessage() {
    const model = CONFIG.model.startsWith('models/') ? CONFIG.model : 'models/' + CONFIG.model;
    return JSON.stringify({
      setup: {
        model: model,
        generationConfig: { responseModalities: ['AUDIO'] },
        systemInstruction: { parts: [{ text: SYSTEM_INSTRUCTION }] },
        realtimeInputConfig: {
          automaticActivityDetection: {
            endOfSpeechSensitivity: 'END_SENSITIVITY_HIGH',
            silenceDurationMs: 800,
          },
        },
      },
    });
  }

  function sendInstruction(text) {
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(
        JSON.stringify({
          clientContent: { turns: [{ role: 'user', parts: [{ text: text }] }], turnComplete: true },
        })
      );
    }
  }

  function sendGreet() {
    sendInstruction(
      '(Begin the conversation now: greet me warmly in one short sentence and ask one easy question about how my day is going.)'
    );
  }

  function sendWrapUpCue() {
    sendInstruction('(We have enough for now — please give one brief warm closing and stop talking.)');
  }

  function openGeminiSession() {
    const url = CONFIG.wsUrl + '?access_token=' + encodeURIComponent(CONFIG.clientSecret);
    ws = new WebSocket(url);
    ws.binaryType = 'arraybuffer';
    ws.onopen = () => ws.send(setupMessage());
    ws.onmessage = (ev) => onGeminiMessage(ev.data);
    ws.onerror = () => setStatus('Connection error — please try again.');
    ws.onclose = () => {
      if (started && !finished) {
        setStatus('Connection closed unexpectedly — please try again.');
        finalizeAndSend();
      }
    };
  }

  function onGeminiMessage(data) {
    if (typeof data === 'string') return onGeminiServer(data);
    if (data instanceof ArrayBuffer) return onGeminiServer(new TextDecoder().decode(data));
    if (typeof Blob !== 'undefined' && data instanceof Blob) {
      data.text().then(onGeminiServer).catch(() => {});
    }
  }

  function onGeminiServer(raw) {
    let msg;
    try {
      msg = JSON.parse(raw);
    } catch (e) {
      return;
    }

    if ('setupComplete' in msg) {
      setupDone = true;
      setStatus('Connected — starting conversation...');
      if (greetPending) {
        greetPending = false;
        sendGreet();
      }
      return;
    }

    const sc = msg.serverContent;
    if (!sc) return;

    const parts = (sc.modelTurn && sc.modelTurn.parts) || [];
    for (const p of parts) {
      if (p.inlineData && p.inlineData.data) {
        if (!speaking) {
          speaking = true;
          updateProgressUI();
        }
        playPcm(b64decode(p.inlineData.data));
      }
    }

    if (sc.interrupted) {
      lastSource = null;
      closeGate();
      return;
    }

    if (sc.turnComplete) {
      const last = lastSource;
      if (last) {
        lastSource = null;
        last.onended = () => closeGate();
      } else {
        closeGate();
      }
    }
  }

  function closeGate() {
    if (!speaking) {
      // No agent audio was actually playing (e.g. a text-only ack) — if we
      // were waiting to wrap up, finalize now since there is nothing to wait for.
      if (wrappingUp) finalizeAfterWrapUp();
      return;
    }
    speaking = false;
    updateProgressUI();
    if (wrappingUp) finalizeAfterWrapUp();
  }

  function playPcm(pcmBuf) {
    if (!audioCtxOut) return;
    const i16 = new Int16Array(pcmBuf);
    const f32 = new Float32Array(i16.length);
    for (let i = 0; i < i16.length; i++) f32[i] = i16[i] / 0x8000;
    const buf = audioCtxOut.createBuffer(1, f32.length, PLAYBACK_RATE);
    buf.copyToChannel(f32, 0);
    const node = audioCtxOut.createBufferSource();
    node.buffer = buf;
    node.connect(audioCtxOut.destination);
    const t = Math.max(audioCtxOut.currentTime, playHead);
    node.start(t);
    playHead = t + buf.duration;
    lastSource = node;
  }

  // ---------------------------------------------------------------------
  // Session lifecycle
  // ---------------------------------------------------------------------
  async function startSession() {
    if (started) return;
    if (!CONFIG.clientSecret || !CONFIG.wsUrl || !CONFIG.model) {
      setStatus('Voice check-in is not configured (missing Gemini credentials).');
      return;
    }

    if (els.startBtn) els.startBtn.disabled = true; // guard against double-click races
    setStatus('Requesting microphone...');
    try {
      micStream = await navigator.mediaDevices.getUserMedia({
        audio: { echoCancellation: true, noiseSuppression: true, autoGainControl: true },
      });
    } catch (err) {
      setStatus('Microphone permission denied: ' + err.message);
      if (els.startBtn) els.startBtn.disabled = false;
      return;
    }

    try {
      audioCtxIn = new (window.AudioContext || window.webkitAudioContext)();
      await audioCtxIn.audioWorklet.addModule('./emotion-worklet.js');
    } catch (err) {
      setStatus('Failed to initialize audio: ' + err.message);
      cleanup();
      if (els.startBtn) els.startBtn.disabled = false;
      return;
    }

    const src = audioCtxIn.createMediaStreamSource(micStream);
    workletNode = new AudioWorkletNode(audioCtxIn, 'emotion-processor');
    src.connect(workletNode);
    workletNode.port.onmessage = (ev) => onWorkletFrame(new Int16Array(ev.data));

    audioCtxOut = new AudioContext({ sampleRate: PLAYBACK_RATE });
    try {
      await audioCtxOut.resume();
    } catch (e) {
      /* noop */
    }
    try {
      await audioCtxIn.resume();
    } catch (e) {
      /* noop */
    }
    playHead = 0;

    started = true;
    finished = false;
    wrappingUp = false;
    startTimeMs = Date.now();
    pcmChunks = [];
    speechElapsedS = 0;
    setupDone = false;
    greetPending = true; // greet as soon as setup is acked

    setStatus('Connecting...');
    if (els.wrapUpBtn) els.wrapUpBtn.disabled = false;
    openGeminiSession();

    progressTimer = setInterval(updateProgressUI, 400);
    updateProgressUI();
  }

  function wrapUp() {
    if (!started || finished || wrappingUp) return;
    wrappingUp = true;
    setStatus('Wrapping up...');
    updateProgressUI();
    if (progressTimer) {
      clearInterval(progressTimer);
      progressTimer = null;
    }

    if (ws && ws.readyState === WebSocket.OPEN && setupDone) {
      sendWrapUpCue();
      // Safety cap: finalize even if the goodbye audio's onended never fires.
      wrapUpTimeoutHandle = setTimeout(finalizeAfterWrapUp, WRAP_UP_MAX_WAIT_MS);
    } else {
      finalizeAfterWrapUp();
    }
  }

  function finalizeAfterWrapUp() {
    if (finished) return;
    if (wrapUpTimeoutHandle) {
      clearTimeout(wrapUpTimeoutHandle);
      wrapUpTimeoutHandle = null;
    }
    finalizeAndSend();
  }

  function encodeWav(chunks, sampleRate) {
    let totalLen = 0;
    for (const c of chunks) totalLen += c.length;
    const pcm = new Int16Array(totalLen);
    let offset = 0;
    for (const c of chunks) {
      pcm.set(c, offset);
      offset += c.length;
    }

    const bytesPerSample = 2;
    const blockAlign = bytesPerSample; // mono
    const byteRate = sampleRate * blockAlign;
    const dataSize = pcm.length * bytesPerSample;
    const buffer = new ArrayBuffer(44 + dataSize);
    const view = new DataView(buffer);

    function writeString(off, str) {
      for (let i = 0; i < str.length; i++) view.setUint8(off + i, str.charCodeAt(i));
    }

    writeString(0, 'RIFF');
    view.setUint32(4, 36 + dataSize, true);
    writeString(8, 'WAVE');
    writeString(12, 'fmt ');
    view.setUint32(16, 16, true); // fmt chunk size
    view.setUint16(20, 1, true); // PCM format
    view.setUint16(22, 1, true); // channels = mono
    view.setUint32(24, sampleRate, true);
    view.setUint32(28, byteRate, true);
    view.setUint16(32, blockAlign, true);
    view.setUint16(34, 16, true); // bits per sample
    writeString(36, 'data');
    view.setUint32(40, dataSize, true);

    let pcmOffset = 44;
    for (let i = 0; i < pcm.length; i++, pcmOffset += 2) {
      view.setInt16(pcmOffset, pcm[i], true);
    }
    return new Uint8Array(buffer);
  }

  function bytesToBase64(bytes) {
    let binary = '';
    const chunkSize = 0x8000;
    for (let i = 0; i < bytes.length; i += chunkSize) {
      const slice = bytes.subarray(i, i + chunkSize);
      binary += String.fromCharCode.apply(null, slice);
    }
    return btoa(binary);
  }

  function cleanup() {
    try {
      if (ws) ws.close();
    } catch (e) {
      /* noop */
    }
    try {
      if (workletNode) workletNode.disconnect();
    } catch (e) {
      /* noop */
    }
    try {
      if (micStream) micStream.getTracks().forEach((t) => t.stop());
    } catch (e) {
      /* noop */
    }
    try {
      if (audioCtxIn) audioCtxIn.close();
    } catch (e) {
      /* noop */
    }
    try {
      if (audioCtxOut) audioCtxOut.close();
    } catch (e) {
      /* noop */
    }
    ws = null;
    workletNode = null;
    micStream = null;
    audioCtxIn = null;
    audioCtxOut = null;
  }

  function finalizeAndSend() {
    if (finished) return;
    finished = true;
    if (progressTimer) {
      clearInterval(progressTimer);
      progressTimer = null;
    }
    const wavBytes = encodeWav(pcmChunks, SR);
    const audioB64 = bytesToBase64(wavBytes);
    setStatus('Done - ' + speechElapsedS.toFixed(0) + 's of speech collected.');
    updateProgressUI();
    cleanup();
    if (els.startBtn) els.startBtn.disabled = false;
    if (els.wrapUpBtn) els.wrapUpBtn.disabled = true;
    setComponentValue({ audio_b64: audioB64, speech_elapsed_s: speechElapsedS });
  }

  if (els.startBtn) els.startBtn.addEventListener('click', startSession);
  if (els.wrapUpBtn) els.wrapUpBtn.addEventListener('click', wrapUp);

  // ---------------------------------------------------------------------
  // Streamlit render handling
  // ---------------------------------------------------------------------
  function onRender(event) {
    if (!event.data || event.data.type !== 'streamlit:render') return;
    const args = event.data.args || {};
    if (typeof args.target_speech_s === 'number') CONFIG.targetSpeechS = args.target_speech_s;
    if (typeof args.timeout_s === 'number') CONFIG.timeoutS = args.timeout_s;
    if (typeof args.client_secret === 'string') CONFIG.clientSecret = args.client_secret;
    if (typeof args.model === 'string') CONFIG.model = args.model;
    // NOTE: voice selection is captured but not yet wired into setupMessage()
    // — the reference implementation this was ported from does not send a
    // voice/speechConfig field either (marked // VERIFY there); adding one
    // speculatively risks a 1007 "unknown field" close. Revisit once the
    // exact field path is confirmed against current Gemini Live docs.
    if (typeof args.voice === 'string') CONFIG.voice = args.voice;
    if (typeof args.ws_url === 'string') CONFIG.wsUrl = args.ws_url;
    setFrameHeight(document.documentElement.scrollHeight || 220);
  }
  window.addEventListener('message', onRender);

  updateProgressUI();
  setFrameHeight(220);
  componentReady();
})();
