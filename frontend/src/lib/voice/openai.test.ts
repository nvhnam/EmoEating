// frontend/src/lib/voice/openai.test.ts
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import type { RealtimeToken } from '$lib/api';

// ---------- Mock RTCPeerConnection ----------
class MockDataChannel {
  readyState: 'connecting' | 'open' | 'closing' | 'closed' = 'open';
  sent: string[] = [];
  onmessage: ((e: { data: string }) => void) | null = null;
  send(data: string) { this.sent.push(data); }
  close() { this.readyState = 'closed'; }
}

class MockPeerConnection {
  _dc = new MockDataChannel();
  ontrack: ((e: { streams: MediaStream[] }) => void) | null = null;
  addTrack = vi.fn();
  createDataChannel = vi.fn(() => this._dc);
  createOffer = vi.fn().mockResolvedValue({ sdp: 'v=0\r\nfake offer', type: 'offer' as RTCSdpType });
  setLocalDescription = vi.fn().mockResolvedValue(undefined);
  setRemoteDescription = vi.fn().mockResolvedValue(undefined);
  close = vi.fn();
}

let mockPc: MockPeerConnection;

const token: RealtimeToken = { provider: 'openai', client_secret: 'eph-123', model: 'm', voice: 'alloy' };

beforeEach(() => {
  mockPc = new MockPeerConnection();
  vi.stubGlobal('RTCPeerConnection', vi.fn(function () { return mockPc; }));
  vi.stubGlobal('fetch', vi.fn(async (url: RequestInfo) => {
    const u = String(url);
    if (u.includes('openai.com')) {
      return { ok: true, text: async () => 'v=0\r\nfake answer' } as Response;
    }
    throw new Error(`Unexpected fetch: ${u}`);
  }));
  vi.spyOn(document, 'createElement').mockImplementation((tag) => {
    if (tag === 'audio') return { autoplay: false, srcObject: null } as unknown as HTMLElement;
    return document.createElement(tag);
  });
});

afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

// Import AFTER globals are stubbed so the module sees them
const { OpenAIRealtimeSession } = await import('./openai');

function fakeStream(): MediaStream {
  return { getAudioTracks: () => [{}] } as unknown as MediaStream;
}

describe('OpenAIRealtimeSession', () => {
  it('does NOT fetch /api/realtime/token — the token is injected', async () => {
    const session = new OpenAIRealtimeSession(token, {});
    await session.start(fakeStream());
    const calls = vi.mocked(fetch).mock.calls;
    const tokenCall = calls.find(([u]) => String(u).includes('/api/realtime/token'));
    expect(tokenCall).toBeUndefined();
    session.close();
  });

  it('uses the ephemeral client_secret as Bearer — real key never appears', async () => {
    const session = new OpenAIRealtimeSession(token, {});
    await session.start(fakeStream());
    const calls = vi.mocked(fetch).mock.calls;
    const sdpCall = calls.find(([u]) => String(u).includes('openai.com'));
    expect(sdpCall).toBeDefined();
    const auth = (sdpCall![1]?.headers as Record<string, string>)?.Authorization ?? '';
    expect(auth).toBe('Bearer eph-123');
    session.close();
  });

  it('exchanges SDP offer/answer with the peer connection', async () => {
    const session = new OpenAIRealtimeSession(token, {});
    await session.start(fakeStream());
    expect(mockPc.createOffer).toHaveBeenCalled();
    expect(mockPc.setLocalDescription).toHaveBeenCalled();
    expect(mockPc.setRemoteDescription).toHaveBeenCalledWith(
      expect.objectContaining({ type: 'answer' })
    );
    session.close();
  });

  it('fires onAgentSpeaking(true) on output_audio_buffer.started', async () => {
    const onAgentSpeaking = vi.fn();
    const session = new OpenAIRealtimeSession(token, { onAgentSpeaking });
    await session.start(fakeStream());
    mockPc._dc.onmessage!({ data: JSON.stringify({ type: 'output_audio_buffer.started' }) });
    expect(onAgentSpeaking).toHaveBeenCalledWith(true);
    session.close();
  });

  it('fires onAgentSpeaking(false) on response.audio.done', async () => {
    const onAgentSpeaking = vi.fn();
    const session = new OpenAIRealtimeSession(token, { onAgentSpeaking });
    await session.start(fakeStream());
    mockPc._dc.onmessage!({ data: JSON.stringify({ type: 'response.audio.done' }) });
    expect(onAgentSpeaking).toHaveBeenCalledWith(false);
    session.close();
  });

  it('sendInstruction sends a conversation item create message over the data channel', async () => {
    const session = new OpenAIRealtimeSession(token, {});
    await session.start(fakeStream());
    session.sendInstruction('wrap up warmly');
    expect(mockPc._dc.sent.length).toBeGreaterThan(0);
    const msg = JSON.parse(mockPc._dc.sent[0]);
    expect(msg.type).toBe('conversation.item.create');
    expect(msg.item.content[0].text).toBe('wrap up warmly');
    session.close();
  });

  it('close() tears down the peer connection and data channel', async () => {
    const session = new OpenAIRealtimeSession(token, {});
    await session.start(fakeStream());
    session.close();
    expect(mockPc.close).toHaveBeenCalled();
    expect(mockPc._dc.readyState).toBe('closed');
  });
});
