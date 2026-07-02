import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { EmotionTap } from './emotionTap';

// ---------- Mock WebSocket ----------
class MockWebSocket {
  static OPEN = 1;
  static CONNECTING = 0;
  static CLOSED = 3;
  readyState = MockWebSocket.OPEN;
  binaryType = 'arraybuffer';
  url: string;
  sent: Array<string | ArrayBuffer> = [];
  onmessage: ((e: { data: unknown }) => void) | null = null;
  onopen: (() => void) | null = null;
  onerror: ((e: unknown) => void) | null = null;
  onclose: (() => void) | null = null;
  constructor(url: string) { this.url = url; }
  send(data: string | ArrayBuffer) { this.sent.push(data); }
  close() { this.readyState = MockWebSocket.CLOSED; }
}

// ---------- Mock AudioWorkletNode ----------
class MockWorkletNode {
  port = {
    onmessage: null as ((e: { data: ArrayBuffer }) => void) | null
  };
  connect(_dest: unknown) {}
  disconnect() {}
}

// ---------- Mock AudioContext ----------
class MockAudioContext {
  audioWorklet = { addModule: vi.fn().mockResolvedValue(undefined) };
  destination = {};
  _workletNode: MockWorkletNode | null = null;
  createMediaStreamSource(_stream: unknown) {
    return { connect: vi.fn(), disconnect: vi.fn() };
  }
  close() { return Promise.resolve(); }
}

let mockWs: MockWebSocket;
let mockCtx: MockAudioContext;

beforeEach(() => {
  mockCtx = new MockAudioContext();
  // Vitest 4.x requires regular functions (not arrow fns) for constructor mocks
  vi.stubGlobal('AudioContext', vi.fn(function () { return mockCtx; }));
  vi.stubGlobal('AudioWorkletNode', vi.fn(function (_ctx: unknown, _name: string) {
    const node = new MockWorkletNode();
    mockCtx._workletNode = node;
    return node;
  }));
  const wsMockFn = vi.fn(function (url: string) {
    mockWs = new MockWebSocket(url);
    return mockWs;
  });
  // Carry over static constants so the implementation can read WebSocket.OPEN
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

function fakeStream(): MediaStream {
  return { getAudioTracks: () => [] } as unknown as MediaStream;
}

describe('EmotionTap', () => {
  it('opens a ws:// WebSocket URL derived from PUBLIC_API_BASE', async () => {
    const tap = new EmotionTap({});
    await tap.start(fakeStream());
    expect(mockWs.url).toMatch(/^ws/);
    expect(mockWs.url).toContain('/ws/emotion');
    tap.close();
  });

  it('sends worklet Int16 frames as binary over WebSocket', async () => {
    const tap = new EmotionTap({});
    await tap.start(fakeStream());
    const buf = new ArrayBuffer(320);
    mockCtx._workletNode!.port.onmessage!({ data: buf });
    expect(mockWs.sent).toContain(buf);
    tap.close();
  });

  it('setAgentSpeaking sends JSON control message', async () => {
    const tap = new EmotionTap({});
    await tap.start(fakeStream());
    tap.setAgentSpeaking(true);
    const ctrl = mockWs.sent.find((s) => typeof s === 'string' && s.includes('agent_speaking'));
    expect(ctrl).toBeDefined();
    expect(JSON.parse(ctrl as string)).toEqual({ type: 'agent_speaking', value: true });
    tap.close();
  });

  it('abort() sends abort control then closes', async () => {
    const tap = new EmotionTap({});
    await tap.start(fakeStream());
    tap.abort();
    const ctrl = mockWs.sent.find((s) => typeof s === 'string' && s.includes('abort'));
    expect(ctrl).toBeDefined();
    expect(JSON.parse(ctrl as string)).toEqual({ type: 'abort' });
    expect(mockWs.readyState).toBe(MockWebSocket.CLOSED);
  });

  it('parses done message and calls onDone with InferResult', async () => {
    const onDone = vi.fn();
    const tap = new EmotionTap({ onDone });
    await tap.start(fakeStream());
    const infer = { emotion_probs: { sad: 0.7 }, valence: -0.7, arousal: -0.5, zone: 'NEG_DEACTIVE' };
    mockWs.onmessage!({ data: JSON.stringify({ type: 'done', infer }) });
    expect(onDone).toHaveBeenCalledWith(infer);
    tap.close();
  });

  it('parses tick message and calls onTick', async () => {
    const onTick = vi.fn();
    const tap = new EmotionTap({ onTick });
    await tap.start(fakeStream());
    mockWs.onmessage!({ data: JSON.stringify({ type: 'tick', confidence: 0.6, elapsed: 20 }) });
    expect(onTick).toHaveBeenCalledWith({ confidence: 0.6, elapsed: 20 });
    tap.close();
  });

  it('parses safety_flag message and calls onSafetyFlag', async () => {
    const onSafetyFlag = vi.fn();
    const tap = new EmotionTap({ onSafetyFlag });
    await tap.start(fakeStream());
    mockWs.onmessage!({ data: JSON.stringify({ type: 'safety_flag' }) });
    expect(onSafetyFlag).toHaveBeenCalledOnce();
    tap.close();
  });

  it('setAgentSpeaking(true) is buffered while CONNECTING and flushed on open', async () => {
    const tap = new EmotionTap({});
    await tap.start(fakeStream());
    // Simulate WS still in CONNECTING state
    mockWs.readyState = MockWebSocket.CONNECTING;
    tap.setAgentSpeaking(true);
    // Nothing sent yet — message is buffered
    const sentWhileConnecting = mockWs.sent.filter(
      (s) => typeof s === 'string' && s.includes('agent_speaking')
    );
    expect(sentWhileConnecting).toHaveLength(0);
    // Fire onopen → pending queue is flushed
    mockWs.readyState = MockWebSocket.OPEN;
    mockWs.onopen!();
    const ctrl = mockWs.sent.find(
      (s) => typeof s === 'string' && s.includes('agent_speaking')
    );
    expect(ctrl).toBeDefined();
    expect(JSON.parse(ctrl as string)).toEqual({ type: 'agent_speaking', value: true });
    tap.close();
  });

  it('setAgentSpeaking(false) sends correct JSON with value false', async () => {
    const tap = new EmotionTap({});
    await tap.start(fakeStream());
    tap.setAgentSpeaking(false);
    const ctrl = mockWs.sent.find(
      (s) => typeof s === 'string' && s.includes('agent_speaking')
    );
    expect(ctrl).toBeDefined();
    expect(JSON.parse(ctrl as string)).toEqual({ type: 'agent_speaking', value: false });
    tap.close();
  });

  it('abort() while CONNECTING still calls close()', async () => {
    const tap = new EmotionTap({});
    await tap.start(fakeStream());
    mockWs.readyState = MockWebSocket.CONNECTING;
    tap.abort();
    // close() must have been called regardless of buffering
    expect(mockWs.readyState).toBe(MockWebSocket.CLOSED);
  });
});
