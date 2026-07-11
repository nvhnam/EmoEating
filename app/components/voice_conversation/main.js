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
 * into the future via a playHead pointer. armGateWatchdog()/AGENT_TURN_MAX_MS
 * is a bounded safety net in case that onended/turnComplete signal is ever
 * dropped or delayed — without it, a single missed close silently wedges
 * the gate shut for the rest of the session (mic frames stop being sent
 * AND the waveform stops reflecting the user's mic, since both are gated
 * by the same `speaking` flag).
 *
 * ensureAudioContextsRunning()/scheduleMicHealthCheck() guard a separate,
 * unrelated failure mode: getUserMedia()'s permission prompt and
 * audioWorklet.addModule()'s network fetch are both async steps that run
 * BEFORE audioCtxIn.resume() is ever called, in a function invoked from a
 * user gesture (the mic button click) — on some browsers that's enough
 * intervening async work to silently erode the gesture association, so
 * resume() can leave audioCtxIn (mic capture) permanently suspended even
 * though audioCtxOut (agent playback) resumes fine. Symptom: you can hear
 * the agent, but your own mic frames never reach the worklet at all —
 * nothing is sent to Gemini, and analyserIn reads frozen data, so the
 * waveform never reflects your voice either.
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
    targetSpeechS: 30,
    timeoutS: 50,
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

  // ---------------------------------------------------------------------
  // Waveform visualization — purely presentational, read-only observers of
  // the state above (speaking/started/finished). Never writes VAD/gate
  // state and never touches onWorkletFrame / the audio-capture pipeline.
  // analyserIn taps `src` (mic) in parallel to the existing worklet
  // connection; analyserOut is inserted inline between each agent audio
  // buffer and the speakers (see playPcm()).
  // ---------------------------------------------------------------------
  let analyserIn = null;
  let analyserOut = null;
  let waveformCanvas = null;
  let waveformCtx = null;
  let waveformRafId = null;
  let waveformDpr = 1;
  const REDUCED_MOTION = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  const WAVEFORM_BARS = 32;
  const COLOR_USER = '#34496B'; // brand — user is speaking
  const COLOR_AGENT = '#8098B4'; // lighter tint, same hue family — agent is speaking
  const COLOR_IDLE = '#CDD5E1'; // muted blue-grey — idle / no active turn

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
    framesReceived++;
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
    // Before the session starts, startTimeMs is still its 0 initial value,
    // so Date.now() - startTimeMs is ~the current Unix epoch in seconds —
    // guard so idle state reads "0s elapsed" instead of a decade-scale number.
    const elapsedS = started ? (Date.now() - startTimeMs) / 1000 : 0;
    if (els.speechSeconds) els.speechSeconds.textContent = speechElapsedS.toFixed(0) + 's';
    if (els.elapsedSeconds) els.elapsedSeconds.textContent = elapsedS.toFixed(0) + 's';
    if (els.progressBar) {
      const pct = Math.min(100, (speechElapsedS / CONFIG.targetSpeechS) * 100);
      els.progressBar.style.transform = 'scaleX(' + (pct / 100) + ')'; // transform, not width — avoids layout thrash
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
    // Presentational hooks only (mic button ring / waveform color via CSS
    // and drawWaveformFrame()) — no state is read back from these classes.
    document.body.classList.toggle('is-started', started && !finished);
    document.body.classList.toggle('is-speaking', speaking);
    document.body.classList.toggle('is-wrapping', wrappingUp);
    if (REDUCED_MOTION) drawWaveformFrame(); // discrete redraw on each state tick
    // Enforce the wall-clock cap even while the agent is speaking: mic frames are
    // gated off then, so onWorkletFrame()'s maybeAutoWrapUp() cannot fire. progressTimer
    // ticks this every 400ms regardless of who is speaking, so the total-conversation
    // budget is honored within ~0.4s. wrapUp()/maybeAutoWrapUp() are self-guarded
    // (wrappingUp / !started / finished), so this is safe to call unconditionally here.
    if (started && !finished) maybeAutoWrapUp();
  }

  // ---------------------------------------------------------------------
  // Waveform canvas — read-only observer of analyserIn/analyserOut +
  // speaking/started/finished. See the block comment above analyserIn's
  // declaration for the non-interference guarantee.
  // ---------------------------------------------------------------------
  function initWaveformCanvas() {
    waveformCanvas = document.getElementById('waveform');
    if (!waveformCanvas) return;
    waveformCtx = waveformCanvas.getContext('2d');
    resizeWaveformCanvas();
  }

  // Root-cause fix: the canvas backing store used to be sized once, at
  // initWaveformCanvas() time, via getBoundingClientRect() — before the
  // Streamlit iframe has necessarily laid out to its final width. If that
  // first read landed on a 0/near-0 rect, the canvas stayed effectively
  // invisible for the rest of the session since nothing ever resized it.
  // This is now callable repeatedly (ResizeObserver, window resize, and
  // Streamlit's onRender) so a late layout always self-corrects.
  function resizeWaveformCanvas() {
    if (!waveformCanvas) return;
    const rect = waveformCanvas.getBoundingClientRect();
    if (rect.width < 2 || rect.height < 2) return; // not laid out yet; caller retries
    waveformDpr = window.devicePixelRatio || 1;
    const w = Math.max(1, Math.round(rect.width * waveformDpr));
    const h = Math.max(1, Math.round(rect.height * waveformDpr));
    if (w === waveformCanvas.width && h === waveformCanvas.height) return;
    waveformCanvas.width = w;
    waveformCanvas.height = h;
  }

  function drawBars(levels, color) {
    const w = waveformCanvas.width;
    const h = waveformCanvas.height;
    waveformCtx.clearRect(0, 0, w, h);
    waveformCtx.fillStyle = color;
    const gap = w * 0.012;
    const barW = (w - gap * (WAVEFORM_BARS - 1)) / WAVEFORM_BARS;
    const radius = Math.min(barW / 2, 4 * waveformDpr);
    for (let i = 0; i < WAVEFORM_BARS; i++) {
      const amp = Math.max(0.06, levels[i]); // floor so idle still reads as "alive"
      const barH = Math.max(barW, amp * h);
      const x = i * (barW + gap);
      const y = (h - barH) / 2;
      waveformCtx.beginPath();
      if (waveformCtx.roundRect) {
        waveformCtx.roundRect(x, y, barW, barH, radius);
      } else {
        waveformCtx.rect(x, y, barW, barH);
      }
      waveformCtx.fill();
    }
  }

  function levelsFromAnalyser(analyser) {
    const freq = new Uint8Array(analyser.frequencyBinCount);
    analyser.getByteFrequencyData(freq);
    const step = Math.max(1, Math.floor(freq.length / WAVEFORM_BARS));
    const levels = new Array(WAVEFORM_BARS).fill(0);
    for (let i = 0; i < WAVEFORM_BARS; i++) {
      levels[i] = freq[i * step] / 255;
    }
    return levels;
  }

  function levelsIdle(t) {
    // Gentle sine-driven "breathing" pattern — no analyser data needed.
    const levels = new Array(WAVEFORM_BARS).fill(0);
    for (let i = 0; i < WAVEFORM_BARS; i++) {
      const phase = t / 900 + i * 0.35;
      levels[i] = 0.08 + 0.05 * (0.5 + 0.5 * Math.sin(phase));
    }
    return levels;
  }

  function drawWaveformFrame() {
    if (!waveformCtx) return;
    const active = started && !finished;
    if (active && speaking && analyserOut) {
      drawBars(levelsFromAnalyser(analyserOut), COLOR_AGENT);
    } else if (active && !speaking && analyserIn) {
      drawBars(levelsFromAnalyser(analyserIn), COLOR_USER);
    } else {
      drawBars(levelsIdle(Date.now()), COLOR_IDLE);
    }
  }

  function waveformLoop() {
    drawWaveformFrame();
    waveformRafId = requestAnimationFrame(waveformLoop);
  }

  function startWaveformLoop() {
    // Intentionally never stopped: it's cheap (32 rects/frame), always
    // wanted (idle breathing → listening → agent-speaking → idle again),
    // and the component is torn down as a whole iframe on remount
    // (Python increments key=f"voice_conv_{seq}"), which naturally kills
    // this loop with it — no separate stop/cleanup call needed.
    if (REDUCED_MOTION || waveformRafId) return;
    waveformLoop();
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
          armGateWatchdog();
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

  // Safety net: the gate is designed to reopen via AudioBufferSourceNode's
  // onended firing after turnComplete (see the file-level doc comment) —
  // correct, but entirely dependent on that event actually firing. If it
  // doesn't (dropped/malformed turnComplete, a browser onended quirk, etc.)
  // `speaking` stays true forever: onWorkletFrame's gate check then silently
  // drops every mic frame (nothing reaches Gemini) and the waveform is stuck
  // showing the now-silent agent analyser instead of the user's mic — this
  // reproduces exactly as "AI doesn't respond, waveform frozen." A generous
  // but bounded timeout guarantees the gate can never wedge the whole session.
  const AGENT_TURN_MAX_MS = 20000;
  let gateWatchdogHandle = null;

  function armGateWatchdog() {
    if (gateWatchdogHandle) clearTimeout(gateWatchdogHandle);
    gateWatchdogHandle = setTimeout(() => {
      console.warn('[voice_conversation] gate watchdog fired — agent turn exceeded', AGENT_TURN_MAX_MS, 'ms without a normal close; forcing the gate back open.');
      closeGate();
    }, AGENT_TURN_MAX_MS);
  }

  function disarmGateWatchdog() {
    if (gateWatchdogHandle) {
      clearTimeout(gateWatchdogHandle);
      gateWatchdogHandle = null;
    }
  }

  function closeGate() {
    disarmGateWatchdog();
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
    node.connect(analyserOut || audioCtxOut.destination); // analyserOut passes audio straight through to destination
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

    // getUserMedia() succeeding doesn't guarantee a usable track — a track
    // can exist but already be 'ended' (device unplugged/revoked mid-prompt)
    // or muted at the OS level. Fail loudly here instead of silently
    // producing zero frames later with no explanation.
    const micTrack = micStream.getAudioTracks()[0];
    if (!micTrack || micTrack.readyState !== 'live') {
      setStatus('No usable microphone track — check your device is connected and not in use by another app, then try again.');
      if (els.startBtn) els.startBtn.disabled = false;
      cleanup();
      return;
    }
    console.info('[voice_conversation] mic track:', micTrack.label || '(unlabeled)', 'muted=', micTrack.muted);

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

    // Waveform taps — parallel fan-out, does not alter src.connect(workletNode)
    // above or anything in the VAD/gate path.
    analyserIn = audioCtxIn.createAnalyser();
    analyserIn.fftSize = 128;
    analyserIn.smoothingTimeConstant = 0.75;
    src.connect(analyserIn);

    audioCtxOut = new AudioContext({ sampleRate: PLAYBACK_RATE });
    analyserOut = audioCtxOut.createAnalyser();
    analyserOut.fftSize = 128;
    analyserOut.smoothingTimeConstant = 0.75;
    analyserOut.connect(audioCtxOut.destination);

    // Root-cause fix: getUserMedia()'s permission prompt and addModule()'s
    // network fetch are both async steps BEFORE we ever call resume() — on
    // several browsers (notably Safari, and Chrome under stricter autoplay
    // policies) that's enough intervening async work to erode the original
    // click's "user activation," so resume() can silently stay suspended
    // despite this whole function running from a click handler. This used
    // to retry ONCE on the next document click, which never fires if the
    // user just starts talking — leaving audioCtxIn (mic capture) suspended
    // forever: zero frames ever reach the worklet, so nothing is sent to
    // Gemini and the waveform analyser reads permanently frozen data. Now:
    // actively verify running state and keep retrying on ANY subsequent
    // interaction (not just one) until both contexts are confirmed running.
    await ensureAudioContextsRunning();
    playHead = 0;

    started = true;
    finished = false;
    wrappingUp = false;
    startTimeMs = Date.now();
    pcmChunks = [];
    speechElapsedS = 0;
    setupDone = false;
    greetPending = true; // greet as soon as setup is acked
    framesReceived = 0;

    setStatus('Connecting...');
    if (els.wrapUpBtn) els.wrapUpBtn.disabled = false;
    openGeminiSession();
    scheduleMicHealthCheck();

    progressTimer = setInterval(updateProgressUI, 400);
    updateProgressUI();
  }

  // ---------------------------------------------------------------------
  // AudioContext resume robustness (see startSession()'s comment above the
  // call site for why this exists) and mic-pipeline health diagnostics.
  // ---------------------------------------------------------------------
  async function ensureAudioContextsRunning() {
    const tryResume = async () => {
      if (audioCtxIn && audioCtxIn.state === 'suspended') {
        try { await audioCtxIn.resume(); } catch (e) { /* noop */ }
      }
      if (audioCtxOut && audioCtxOut.state === 'suspended') {
        try { await audioCtxOut.resume(); } catch (e) { /* noop */ }
      }
    };
    await tryResume();
    console.info('[voice_conversation] AudioContext states after initial resume — in:', audioCtxIn && audioCtxIn.state, 'out:', audioCtxOut && audioCtxOut.state);
    if ((audioCtxIn && audioCtxIn.state === 'suspended') || (audioCtxOut && audioCtxOut.state === 'suspended')) {
      const events = ['click', 'touchstart', 'keydown'];
      const retryHandler = () => {
        tryResume().then(() => {
          const inOk = !audioCtxIn || audioCtxIn.state === 'running';
          const outOk = !audioCtxOut || audioCtxOut.state === 'running';
          if (inOk && outOk) {
            events.forEach((evt) => document.removeEventListener(evt, retryHandler));
          }
        });
      };
      events.forEach((evt) => document.addEventListener(evt, retryHandler));
    }
  }

  let framesReceived = 0;
  let micHealthCheckHandle = null;
  const MIC_HEALTH_CHECK_MS = 4000;

  function scheduleMicHealthCheck() {
    if (micHealthCheckHandle) clearTimeout(micHealthCheckHandle);
    micHealthCheckHandle = setTimeout(() => {
      if (started && !finished && framesReceived === 0) {
        setStatus('Not detecting any microphone input — check the correct device is selected and unmuted, then tap the mic to try again.');
        console.warn(
          '[voice_conversation] no worklet frames received within', MIC_HEALTH_CHECK_MS,
          'ms. audioCtxIn.state =', audioCtxIn && audioCtxIn.state,
          '— if suspended, this is the known resume-erosion issue; if running, check OS-level mic mute/device selection.'
        );
      }
    }, MIC_HEALTH_CHECK_MS);
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
    disarmGateWatchdog();
    if (micHealthCheckHandle) {
      clearTimeout(micHealthCheckHandle);
      micHealthCheckHandle = null;
    }
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
    analyserIn = null;
    analyserOut = null;
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
    // Streamlit sends streamlit:render once the component has actually been
    // mounted/sized — a second resize pass here catches the common case
    // where the very first initWaveformCanvas() call raced the iframe's
    // layout. Math.max floor guards against a transient small scrollHeight
    // collapsing the iframe and clipping the canvas region.
    resizeWaveformCanvas();
    if (waveformCtx) drawWaveformFrame();
    setFrameHeight(Math.max(document.documentElement.scrollHeight || 0, 560));
  }
  window.addEventListener('message', onRender);

  initWaveformCanvas();
  startWaveformLoop();
  updateProgressUI();
  setFrameHeight(560);
  componentReady();

  // Belt-and-suspenders: rescale the canvas backing store whenever its
  // laid-out size changes (iframe resize, orientation change, late fonts
  // shifting layout) — not just once at init.
  if (window.ResizeObserver && waveformCanvas) {
    const waveformResizeObserver = new ResizeObserver(() => {
      resizeWaveformCanvas();
      if (waveformCtx) drawWaveformFrame();
    });
    waveformResizeObserver.observe(waveformCanvas);
  }
  window.addEventListener('resize', () => {
    resizeWaveformCanvas();
    if (waveformCtx) drawWaveformFrame();
  });
})();
