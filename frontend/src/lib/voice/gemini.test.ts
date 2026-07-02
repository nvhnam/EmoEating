import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { GeminiLiveSession } from './gemini';
import type { RealtimeToken } from '$lib/api';

// ---------- Mock WebSocket ----------
class MockWebSocket {
  static OPEN = 1;
  static CONNECTING = 0;
  static CLOSED = 3;
  readyState = MockWebSocket.CONNECTING;
  url: string;
  sent: unknown[] = [];
  onmessage: ((e: { data: unknown }) => void) | null = null;
  onopen: (() => void) | null = null;
  onerror: ((e: unknown) => void) | null = null;
  onclose: (() => void) | null = null;
  close = vi.fn(() => {
    this.readyState = MockWebSocket.CLOSED;
  });
  constructor(url: string) {
    this.url = url;
  }
  send(data: unknown) {
    this.sent.push(data);
  }
}

// ---------- Mock AudioWorkletNode ----------
class MockWorkletNode {
  port = {
    onmessage: null as ((e: { data: ArrayBuffer }) => void) | null
  };
  connect(_dest: unknown) {}
  disconnect = vi.fn();
}

// ---------- Mock AudioContext ----------
class MockAudioContext {
  audioWorklet = { addModule: vi.fn().mockResolvedValue(undefined) };
  destination = {};
  currentTime = 0;
  createBuffer = vi.fn((_ch: number, length: number, _rate: number) => ({
    duration: length / 24000,
    copyToChannel: vi.fn()
  }));
  createBufferSource = vi.fn(() => ({
    buffer: null as unknown,
    connect: vi.fn(),
    start: vi.fn(),
    onended: null as null | (() => void)
  }));
  createMediaStreamSource(_stream: unknown) {
    return { connect: vi.fn(), disconnect: vi.fn() };
  }
  close = vi.fn(() => Promise.resolve());
}

let mockWs: MockWebSocket;
let audioContexts: MockAudioContext[];
let workletNode: MockWorkletNode;

beforeEach(() => {
  audioContexts = [];
  // Vitest 4.x requires regular functions (not arrow fns) for constructor mocks
  vi.stubGlobal(
    'AudioContext',
    vi.fn(function () {
      const ctx = new MockAudioContext();
      audioContexts.push(ctx);
      return ctx;
    })
  );
  vi.stubGlobal(
    'AudioWorkletNode',
    vi.fn(function (_ctx: unknown, _name: string) {
      workletNode = new MockWorkletNode();
      return workletNode;
    })
  );
  const wsMockFn = vi.fn(function (url: string) {
    mockWs = new MockWebSocket(url);
    return mockWs;
  });
  Object.assign(wsMockFn, {
    OPEN: MockWebSocket.OPEN,
    CONNECTING: MockWebSocket.CONNECTING,
    CLOSED: MockWebSocket.CLOSED
  });
  vi.stubGlobal('WebSocket', wsMockFn);
});

afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

const geminiToken: RealtimeToken = {
  provider: 'gemini',
  client_secret: 'eph',
  model: 'gemini-live-2.5-flash-native-audio',
  voice: 'Aoede',
  ws_url: 'wss://x/ws',
  api_version: 'v1alpha'
};

function fakeStream(stopSpy?: () => void): MediaStream {
  return {
    getAudioTracks: () => [{ stop: stopSpy ?? (() => {}) }]
  } as unknown as MediaStream;
}

function b64encode(buf: ArrayBuffer): string {
  let bin = '';
  const bytes = new Uint8Array(buf);
  for (let i = 0; i < bytes.length; i++) bin += String.fromCharCode(bytes[i]);
  return btoa(bin);
}

describe('GeminiLiveSession', () => {
  it('connects with the ephemeral client_secret as ?access_token and sends setup', async () => {
    const session = new GeminiLiveSession(geminiToken, {});
    await session.start(fakeStream());
    // Fix 3a: the WS URL carries the ephemeral token as ?access_token=.
    expect(mockWs.url).toContain('?access_token=');
    expect(mockWs.url).toContain(encodeURIComponent(geminiToken.client_secret));
    mockWs.onopen!();
    const setup = JSON.parse(mockWs.sent[0] as string);
    expect(setup.setup.model).toBe('models/gemini-live-2.5-flash-native-audio');
    // Setup negotiates AUDIO output under generationConfig (the API rejects
    // responseModalities at the setup top level, and enableAffectiveDialog).
    expect(setup.setup.generationConfig.responseModalities).toEqual(['AUDIO']);
    expect(setup.setup.responseModalities).toBeUndefined();
    expect(setup.setup.enableAffectiveDialog).toBeUndefined();
    session.close();
  });

  it('configures fast end-of-turn detection so the agent replies promptly after the user stops', async () => {
    const session = new GeminiLiveSession(geminiToken, {});
    await session.start(fakeStream());
    mockWs.onopen!();
    const setup = JSON.parse(mockWs.sent[0] as string);
    const aad = setup.setup.realtimeInputConfig.automaticActivityDetection;
    expect(aad.endOfSpeechSensitivity).toBe('END_SENSITIVITY_HIGH');
    expect(aad.silenceDurationMs).toBe(800);
    session.close();
  });

  it('forwards a mic worklet frame as a realtimeInput audio blob (16k pcm)', async () => {
    const session = new GeminiLiveSession(geminiToken, {});
    await session.start(fakeStream());
    mockWs.readyState = MockWebSocket.OPEN;
    // Live API protocol: client messages may only flow after the setup ack.
    mockWs.onmessage!({ data: JSON.stringify({ setupComplete: {} }) });
    const samples = new Int16Array([1, 2, 3, 4]);
    workletNode.port.onmessage!({ data: samples.buffer });
    const msg = mockWs.sent
      .map((s) => JSON.parse(s as string))
      .find((m) => m.realtimeInput);
    expect(msg.realtimeInput.audio.mimeType).toBe('audio/pcm;rate=16000');
    expect(typeof msg.realtimeInput.audio.data).toBe('string');
    expect(msg.realtimeInput.audio.data.length).toBeGreaterThan(0);
    // Fix 3b: the base64 payload must decode back to the exact Int16 bytes we fed it.
    const bin = atob(msg.realtimeInput.audio.data);
    const bytes = new Uint8Array(bin.length);
    for (let i = 0; i < bin.length; i++) bytes[i] = bin.charCodeAt(i);
    expect(new Int16Array(bytes.buffer)).toEqual(samples);
    session.close();
  });

  it('holds mic frames until setupComplete (Live API protocol)', async () => {
    const session = new GeminiLiveSession(geminiToken, {});
    await session.start(fakeStream());
    mockWs.readyState = MockWebSocket.OPEN;
    // No setup ack yet — audio racing the setup can degrade/kill the session.
    workletNode.port.onmessage!({ data: new Int16Array([1, 2]).buffer });
    expect(mockWs.sent.map((s) => JSON.parse(s as string)).find((m) => m.realtimeInput)).toBeUndefined();
    session.close();
  });

  it('does not forward mic frames while the agent is audibly speaking (echo defense)', async () => {
    const session = new GeminiLiveSession(geminiToken, {});
    await session.start(fakeStream());
    mockWs.readyState = MockWebSocket.OPEN;
    mockWs.onmessage!({ data: JSON.stringify({ setupComplete: {} }) });

    // Agent turn begins: gate closes — mic frames must NOT reach Gemini (the
    // speaker output is not echo-cancelled, so it would hear itself).
    sendAudio(100, -200, 300);
    workletNode.port.onmessage!({ data: new Int16Array([1, 2]).buffer });
    expect(mockWs.sent.map((s) => JSON.parse(s as string)).find((m) => m.realtimeInput)).toBeUndefined();

    // Turn ends and playback drains: gate re-opens — frames flow again.
    mockWs.onmessage!({ data: JSON.stringify({ serverContent: { turnComplete: true } }) });
    lastBufferSource().onended!();
    workletNode.port.onmessage!({ data: new Int16Array([3, 4]).buffer });
    expect(mockWs.sent.map((s) => JSON.parse(s as string)).find((m) => m.realtimeInput)).toBeDefined();
    session.close();
  });

  // Helpers to drive a single audio part / turn boundary through the server channel.
  function sendAudio(...samples: number[]): void {
    mockWs.onmessage!({
      data: JSON.stringify({
        serverContent: {
          modelTurn: {
            parts: [
              { inlineData: { mimeType: 'audio/pcm;rate=24000', data: b64encode(new Int16Array(samples).buffer) } }
            ]
          }
        }
      })
    });
  }
  function lastBufferSource(): { onended: null | (() => void) } {
    const ctxOut = audioContexts[1];
    const results = ctxOut.createBufferSource.mock.results;
    return results[results.length - 1].value as { onended: null | (() => void) };
  }

  it('plays serverContent audio and opens the echo gate on the first audio part', async () => {
    const onAgentSpeaking = vi.fn();
    const session = new GeminiLiveSession(geminiToken, { onAgentSpeaking });
    await session.start(fakeStream());
    sendAudio(100, -200, 300);
    expect(onAgentSpeaking).toHaveBeenCalledWith(true);
    // playback ctx is the second AudioContext created (ctxOut)
    expect(audioContexts[1].createBuffer).toHaveBeenCalled();
    session.close();
  });

  it('opens the echo gate ONCE per turn even across multiple audio parts', async () => {
    const onAgentSpeaking = vi.fn();
    const session = new GeminiLiveSession(geminiToken, { onAgentSpeaking });
    await session.start(fakeStream());
    sendAudio(100, -200, 300);
    sendAudio(400, 500);
    sendAudio(-600);
    // true must fire exactly once for the whole turn, not per audio part.
    expect(onAgentSpeaking.mock.calls.filter((c) => c[0] === true)).toHaveLength(1);
    session.close();
  });

  it('does NOT close the echo gate synchronously on turnComplete while playback is pending', async () => {
    const onAgentSpeaking = vi.fn();
    const session = new GeminiLiveSession(geminiToken, { onAgentSpeaking });
    await session.start(fakeStream());
    sendAudio(100, -200, 300);
    onAgentSpeaking.mockClear();

    // turnComplete arrives, but the audio is scheduled into the future via playHead.
    mockWs.onmessage!({ data: JSON.stringify({ serverContent: { turnComplete: true } }) });
    // The gate must stay CLOSED (no false yet) so the agent's own voice can't pollute
    // the EmotionTap read while it is still audible.
    expect(onAgentSpeaking).not.toHaveBeenCalledWith(false);

    // Once the last scheduled buffer source actually finishes, the gate re-opens.
    lastBufferSource().onended!();
    expect(onAgentSpeaking).toHaveBeenCalledWith(false);
    session.close();
  });

  it('closes the echo gate immediately on a turnComplete with no pending audio', async () => {
    const onAgentSpeaking = vi.fn();
    const session = new GeminiLiveSession(geminiToken, { onAgentSpeaking });
    await session.start(fakeStream());
    sendAudio(1, 2, 3);
    // First turnComplete defers the close to the scheduled buffer's onended.
    mockWs.onmessage!({ data: JSON.stringify({ serverContent: { turnComplete: true } }) });
    expect(onAgentSpeaking).not.toHaveBeenCalledWith(false);
    onAgentSpeaking.mockClear();

    // A second turnComplete arrives before playback ended — no buffer pending now,
    // so the gate closes immediately rather than hanging open.
    mockWs.onmessage!({ data: JSON.stringify({ serverContent: { turnComplete: true } }) });
    expect(onAgentSpeaking).toHaveBeenCalledWith(false);
    session.close();
  });

  it('interrupted (user barge-in) closes the echo gate immediately', async () => {
    const onAgentSpeaking = vi.fn();
    const session = new GeminiLiveSession(geminiToken, { onAgentSpeaking });
    await session.start(fakeStream());
    sendAudio(100, -200, 300);
    onAgentSpeaking.mockClear();

    mockWs.onmessage!({ data: JSON.stringify({ serverContent: { interrupted: true } }) });
    // The user is talking NOW — gate closes synchronously, no deferral.
    expect(onAgentSpeaking).toHaveBeenCalledWith(false);
    session.close();
  });

  it('sendInstruction sends a clientContent turn', async () => {
    const session = new GeminiLiveSession(geminiToken, {});
    await session.start(fakeStream());
    mockWs.readyState = MockWebSocket.OPEN;
    session.sendInstruction('wrap up');
    const msg = mockWs.sent
      .map((s) => JSON.parse(s as string))
      .find((m) => m.clientContent);
    expect(msg).toEqual({
      clientContent: { turns: [{ role: 'user', parts: [{ text: 'wrap up' }] }], turnComplete: true }
    });
    session.close();
  });

  it('close() closes the WS + playback but does not stop the mic', async () => {
    const stopSpy = vi.fn();
    const session = new GeminiLiveSession(geminiToken, {});
    await session.start(fakeStream(stopSpy));
    session.close();
    expect(mockWs.close).toHaveBeenCalled();
    expect(stopSpy).not.toHaveBeenCalled();
  });
});
