import type { VoiceSession, VoiceSessionCallbacks } from './types';
import type { RealtimeToken } from '$lib/api';

// --- Gemini Live BidiGenerateContent wire shapes — ISOLATED. // VERIFY against current docs.
const GEMINI_INPUT_MIME = 'audio/pcm;rate=16000';
const PLAYBACK_RATE = 24000; // Gemini output PCM sample rate. // VERIFY.
// Keep this text in sync with backend _AGENT_INSTRUCTIONS (realtime.py): same
// scenario, same guardrails (988 Lifeline, no-diagnosis, no-food).
const SYSTEM_INSTRUCTION =
  'You are the friendly check-in host inside EmoEating, a food app that suggests meals ' +
  'matching how the user feels — read from the sound of their voice, never from their words. ' +
  'The user has just opened the menu; this short chat is what personalizes it. Your goal: get ' +
  'them talking warmly and naturally for about a minute so the app can hear how they are ' +
  'doing. Open the conversation yourself: one brief, warm greeting plus one easy question ' +
  'about their day — do not wait for them to speak first. Then follow their lead, one short ' +
  'open question at a time: their day, their energy right now, what has been on their mind, ' +
  'or something they are looking forward to. Keep your own turns to one or two sentences; ' +
  'they should do most of the talking, so invite them to say more. Never discuss, suggest, ' +
  'or ask about food, meals, hunger, or nutrition — the menu handles that after this chat. ' +
  'You are not a therapist and never diagnose. If they mention crisis or serious distress, ' +
  'acknowledge warmly, offer the 988 Suicide & Crisis Lifeline, and end gently. When told to ' +
  'wrap up, give one brief warm closing and stop talking.';

function setupMessage(model: string): string {
  return JSON.stringify({
    setup: {
      model: model.startsWith('models/') ? model : `models/${model}`,
      // responseModalities lives ONLY under generationConfig — the API rejects it
      // at the setup top level (close 1007 "Unknown name responseModalities"). // VERIFY.
      generationConfig: { responseModalities: ['AUDIO'] },
      systemInstruction: { parts: [{ text: SYSTEM_INSTRUCTION }] },
      // End-of-turn tuning: the API default waits a long silence tail before deciding
      // the user finished, which reads as "it keeps listening at me". HIGH sensitivity
      // + an 800ms tail keeps mid-sentence pauses safe while handing the turn over
      // promptly. Field names per https://ai.google.dev/api/live. // VERIFY.
      realtimeInputConfig: {
        automaticActivityDetection: {
          endOfSpeechSensitivity: 'END_SENSITIVITY_HIGH',
          silenceDurationMs: 800
        }
      }
      // NOTE: enableAffectiveDialog is rejected by this API version (1007) and is
      // unnecessary — our emotion2vec pipeline does the affect read, not Gemini. // VERIFY.
    }
  });
}

function b64encode(buf: ArrayBuffer): string {
  let bin = '';
  const bytes = new Uint8Array(buf);
  for (let i = 0; i < bytes.length; i++) bin += String.fromCharCode(bytes[i]);
  return btoa(bin);
}
function b64decode(s: string): ArrayBuffer {
  const bin = atob(s);
  const out = new Uint8Array(bin.length);
  for (let i = 0; i < bin.length; i++) out[i] = bin.charCodeAt(i);
  return out.buffer;
}

export class GeminiLiveSession implements VoiceSession {
  private ws: WebSocket | null = null;
  private ctxIn: AudioContext | null = null;
  private node: AudioWorkletNode | null = null;
  private src: MediaStreamAudioSourceNode | null = null;
  private ctxOut: AudioContext | null = null;
  private agentDest: MediaStreamAudioDestinationNode | null = null;
  private playHead = 0;
  // Echo-gate state: the gate must stay CLOSED (speaking=true) until the agent's
  // audio has actually finished playing, not merely until the turn is marked
  // complete — audio is scheduled into the future via playHead.
  private speaking = false;
  private setupDone = false;
  private greetPending = false;
  private lastSource: AudioBufferSourceNode | null = null;
  private readonly token: RealtimeToken;
  private readonly cbs: VoiceSessionCallbacks;

  constructor(token: RealtimeToken, cbs: VoiceSessionCallbacks) {
    this.token = token;
    this.cbs = cbs;
  }

  async start(stream: MediaStream): Promise<void> {
    const url = `${this.token.ws_url}?access_token=${encodeURIComponent(this.token.client_secret)}`;
    this.ws = new WebSocket(url);
    // Gemini Live delivers server messages as BINARY frames in the browser — take
    // them as ArrayBuffer so we can decode to text before JSON.parse. // VERIFY.
    this.ws.binaryType = 'arraybuffer';
    this.ws.onopen = () => this.ws?.send(setupMessage(this.token.model));
    this.ws.onmessage = (e: MessageEvent) => this._onMessage(e.data);
    this.ws.onerror = () => console.warn('[gemini] websocket error');
    this.ws.onclose = (e: CloseEvent) =>
      console.warn('[gemini] websocket closed', e.code, e.reason);

    this.ctxIn = new AudioContext();
    await this.ctxIn.audioWorklet.addModule('/emotion-worklet.js');
    this.src = this.ctxIn.createMediaStreamSource(stream);
    this.node = new AudioWorkletNode(this.ctxIn, 'emotion-processor');
    this.src.connect(this.node);
    this.node.port.onmessage = (ev: MessageEvent) => {
      if (this.ws?.readyState !== WebSocket.OPEN) return;
      // Live API protocol: no client messages before the setup ack — audio racing
      // setupComplete can degrade or kill the session (and swallow the greeting).
      if (!this.setupDone) return;
      // Echo defense: agent playback goes through WebAudio, which browser echo
      // cancellation does not reference — on speakers the mic hears the agent's
      // own voice. Gate the mic while the agent is audible so Gemini never hears
      // itself (trade-off: barge-in is disabled; acceptable for a short check-in).
      if (this.speaking) return;
      this.ws.send(JSON.stringify({
        realtimeInput: { audio: { data: b64encode(ev.data as ArrayBuffer), mimeType: GEMINI_INPUT_MIME } }
      }));
    };

    this.ctxOut = new AudioContext({ sampleRate: PLAYBACK_RATE });
    // Created after awaits (outside the click gesture) → may start suspended; resume
    // so scheduled agent audio actually plays.
    try { await this.ctxOut.resume?.(); } catch { /* ignore */ }
    try { await this.ctxIn.resume?.(); } catch { /* ignore */ }
    // Expose the agent's audio as a MediaStream so the UI can visualize it.
    try {
      this.agentDest = this.ctxOut.createMediaStreamDestination();
      this.cbs.onAgentStream?.(this.agentDest.stream);
    } catch {
      /* visualization is non-essential */
    }
  }

  // Normalize the WS frame to a JSON string, whatever framing the server used.
  private _onMessage(data: unknown): void {
    if (typeof data === 'string') this._onServer(data);
    else if (data instanceof ArrayBuffer) this._onServer(new TextDecoder().decode(data));
    else if (typeof Blob !== 'undefined' && data instanceof Blob)
      void data.text().then((t) => this._onServer(t)).catch(() => {});
  }

  private _onServer(raw: string): void {
    let msg: {
      serverContent?: { modelTurn?: { parts?: Array<{ inlineData?: { data?: string } }> }; turnComplete?: boolean; interrupted?: boolean };
      setupComplete?: unknown;
    };
    try { msg = JSON.parse(raw); } catch { return; }
    if ('setupComplete' in msg) {
      // Setup acked — safe to send client turns now. Flush a queued greeting.
      this.setupDone = true;
      if (this.greetPending) {
        this.greetPending = false;
        this._sendGreet();
      }
      return;
    }
    const sc = msg.serverContent;
    if (!sc) {
      // Surface anything unexpected (errors, unhandled shapes) to aid live debugging.
      console.debug('[gemini] server message:', raw.slice(0, 300));
      return;
    }
    for (const p of sc.modelTurn?.parts ?? []) {
      if (p.inlineData?.data) {
        // Open the gate ONCE at the start of a turn (first audio part), not per part.
        if (!this.speaking) {
          this.speaking = true;
          this.cbs.onAgentSpeaking?.(true);
        }
        this._playPcm(b64decode(p.inlineData.data));
      }
    }
    if (sc.interrupted) {
      // User barge-in: the user is talking NOW, so close the gate immediately and
      // drop any deferred close from scheduled (but interrupted) playback.
      this.lastSource = null;
      this._closeGate();
      return;
    }
    if (sc.turnComplete) {
      const last = this.lastSource;
      if (last) {
        // Defer the gate close to ACTUAL playback end: audio is scheduled into the
        // future via playHead, so closing now would re-open the EmotionTap while the
        // agent is still audible and pollute the emotion read.
        this.lastSource = null;
        last.onended = () => this._closeGate();
      } else {
        // No audio scheduled this turn → nothing to wait for, close immediately.
        this._closeGate();
      }
    }
  }

  private _closeGate(): void {
    if (!this.speaking) return;
    this.speaking = false;
    this.cbs.onAgentSpeaking?.(false);
  }

  private _playPcm(pcm: ArrayBuffer): void {
    if (!this.ctxOut) return;
    const i16 = new Int16Array(pcm);
    const f32 = new Float32Array(i16.length);
    for (let i = 0; i < i16.length; i++) f32[i] = i16[i] / 0x8000;
    const buf = this.ctxOut.createBuffer(1, f32.length, PLAYBACK_RATE);
    buf.copyToChannel(f32, 0);
    const node = this.ctxOut.createBufferSource();
    node.buffer = buf;
    node.connect(this.ctxOut.destination);
    if (this.agentDest) node.connect(this.agentDest);
    const t = Math.max(this.ctxOut.currentTime, this.playHead);
    node.start(t);
    this.playHead = t + buf.duration;
    this.lastSource = node;
  }

  sendInstruction(text: string): void {
    if (this.ws?.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify({
        clientContent: { turns: [{ role: 'user', parts: [{ text }] }], turnComplete: true }
      }));
    }
  }

  // Kick off the agent's opening turn. Must run after setupComplete; queue if not yet.
  private _sendGreet(): void {
    this.sendInstruction(
      '(Begin the conversation now: greet me warmly in one short sentence and ask one easy question about how my day is going.)'
    );
  }

  greet(): void {
    if (this.setupDone) this._sendGreet();
    else this.greetPending = true;
  }

  close(): void {
    try { this.ws?.close(); } catch { /* noop */ }
    this.node?.disconnect();
    this.src?.disconnect();
    void this.ctxIn?.close();
    void this.ctxOut?.close();
    // The shared mic MediaStream is owned by /converse — do NOT stop its tracks here.
    this.ws = null; this.node = null; this.src = null; this.ctxIn = null; this.ctxOut = null;
  }
}
