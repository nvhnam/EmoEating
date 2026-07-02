// frontend/src/lib/voice/openai.ts
/**
 * OpenAIRealtimeSession — WebRTC peer to the OpenAI Realtime API.
 *
 * OPEN ITEM: Before wiring, verify the current SDP endpoint URL and request
 * shape at https://platform.openai.com/docs/guides/realtime-webrtc — isolate
 * any changes to OPENAI_SDP_BASE / the OAI_EVENT_* constants and the fetch
 * call in _exchangeSdp() below. These are the only OpenAI-specific shapes;
 * each is a one-line change if the API drifts.
 */
import type { RealtimeToken } from '$lib/api';
import type { VoiceSession, VoiceSessionCallbacks } from './types';

// ---------------------------------------------------------------------------
// OpenAI Realtime WebRTC specifics — ISOLATED. // VERIFY against current docs.
// Verified 2026-06-27 against https://developers.openai.com/api/docs/guides/realtime-webrtc
// (platform.openai.com/docs/guides/realtime-webrtc → 301 redirect).
// ---------------------------------------------------------------------------

// SDP POST target for the browser→OpenAI offer/answer exchange.
// VERIFY against current OpenAI Realtime WebRTC docs.
const OPENAI_SDP_BASE = 'https://api.openai.com/v1/realtime/calls';

// Data-channel server event: agent began emitting audio. // VERIFY against current docs.
const OAI_EVENT_AUDIO_STARTED = 'output_audio_buffer.started';
// Data-channel server events: agent finished / audio buffer drained. // VERIFY against current docs.
const OAI_EVENT_AUDIO_STOPPED = 'output_audio_buffer.stopped';
const OAI_EVENT_AUDIO_DONE = 'response.audio.done';
// Data-channel server event carrying the user's transcribed speech (G3 hook). // VERIFY against current docs.
const OAI_EVENT_INPUT_TRANSCRIPTION = 'conversation.item.input_audio_transcription.completed';

type DataChannelMsg = { type: string; transcript?: string };

export class OpenAIRealtimeSession implements VoiceSession {
  private pc: RTCPeerConnection | null = null;
  private dc: RTCDataChannel | null = null;
  private audioEl: HTMLAudioElement | null = null;
  private greetPending = false;
  private readonly token: RealtimeToken;
  private readonly callbacks: VoiceSessionCallbacks;

  constructor(token: RealtimeToken, callbacks: VoiceSessionCallbacks) {
    this.token = token;
    this.callbacks = callbacks;
  }

  private async _exchangeSdp(offerSdp: string, token: RealtimeToken): Promise<string> {
    const res = await fetch(
      `${OPENAI_SDP_BASE}?model=${encodeURIComponent(token.model)}`,
      {
        method: 'POST',
        headers: {
          Authorization: `Bearer ${token.client_secret}`,
          'Content-Type': 'application/sdp'
        },
        body: offerSdp
      }
    );
    if (!res.ok) throw new Error(`SDP exchange failed: ${res.status}`);
    return res.text();
  }

  async start(stream: MediaStream): Promise<void> {
    this.pc = new RTCPeerConnection();

    // Play agent audio in the page (element not appended to DOM — just used for playback)
    this.audioEl = document.createElement('audio') as HTMLAudioElement;
    this.audioEl.autoplay = true;
    this.pc.ontrack = (e: RTCTrackEvent) => {
      if (this.audioEl) this.audioEl.srcObject = e.streams[0];
      this.callbacks.onAgentStream?.(e.streams[0]);
    };

    for (const track of stream.getAudioTracks()) {
      this.pc.addTrack(track, stream);
    }

    this.dc = this.pc.createDataChannel('oai-events');
    this.dc.onmessage = (e: MessageEvent) => this._handleEvent(e.data as string);
    this.dc.onopen = () => {
      if (this.greetPending) {
        this.greetPending = false;
        this._sendGreet();
      }
    };

    const offer = await this.pc.createOffer();
    await this.pc.setLocalDescription(offer);

    const answerSdp = await this._exchangeSdp(offer.sdp ?? '', this.token);
    await this.pc.setRemoteDescription({ type: 'answer', sdp: answerSdp });
  }

  private _handleEvent(raw: string): void {
    let msg: DataChannelMsg;
    try {
      msg = JSON.parse(raw) as DataChannelMsg;
    } catch {
      return;
    }

    if (msg.type === OAI_EVENT_AUDIO_STARTED) {
      this.callbacks.onAgentSpeaking?.(true);
    } else if (msg.type === OAI_EVENT_AUDIO_STOPPED || msg.type === OAI_EVENT_AUDIO_DONE) {
      this.callbacks.onAgentSpeaking?.(false);
    } else if (msg.type === OAI_EVENT_INPUT_TRANSCRIPTION) {
      // G3 INTEGRATION HOOK (deferred): the user's transcribed speech arrives
      // here. The crisis-screening logic (spec §G3) inspects `msg.transcript`
      // and, on a crisis match, surfaces the crisis screen. Wire the screen
      // during integration; the event hook point is established here.
      // e.g. this.callbacks.onTranscript?.(msg.transcript ?? '');
    }
  }

  // Ask the model to produce the opening turn (the session instructions tell it to
  // greet warmly first). Waits for the data channel if it isn't open yet.
  private _sendGreet(): void {
    this.dc?.send(JSON.stringify({ type: 'response.create' }));
  }

  greet(): void {
    if (this.dc?.readyState === 'open') this._sendGreet();
    else this.greetPending = true;
  }

  sendInstruction(text: string): void {
    if (this.dc?.readyState === 'open') {
      this.dc.send(
        JSON.stringify({
          type: 'conversation.item.create',
          item: {
            type: 'message',
            role: 'user',
            content: [{ type: 'input_text', text }]
          }
        })
      );
    }
  }

  close(): void {
    this.dc?.close();
    this.pc?.close();
    if (this.audioEl) {
      this.audioEl.srcObject = null;
      this.audioEl = null;
    }
    this.dc = null;
    this.pc = null;
  }
}
