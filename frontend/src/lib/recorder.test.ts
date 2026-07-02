import { describe, it, expect, vi, beforeEach } from 'vitest';
import { AudioRecorder } from './recorder';

class FakeMediaRecorder {
  ondataavailable: ((e: { data: Blob }) => void) | null = null;
  onstop: (() => void) | null = null;
  mimeType = 'audio/webm';
  constructor(public stream: { getTracks: () => { stop: () => void }[] }) {}
  start() {
    this.ondataavailable?.({ data: new Blob(['chunk'], { type: 'audio/webm' }) });
  }
  stop() {
    this.onstop?.();
  }
}

let track: { stop: ReturnType<typeof vi.fn> };
let getUserMedia: ReturnType<typeof vi.fn>;

beforeEach(() => {
  vi.stubGlobal('MediaRecorder', FakeMediaRecorder as unknown as typeof MediaRecorder);
  track = { stop: vi.fn() };
  getUserMedia = vi.fn(async () => ({ getTracks: () => [track] }));
  vi.stubGlobal('navigator', { mediaDevices: { getUserMedia } });
});

describe('AudioRecorder', () => {
  it('captures a blob between start and stop', async () => {
    const rec = new AudioRecorder();
    await rec.start();
    expect(rec.recording).toBe(true);
    const blob = await rec.stop();
    expect(blob.size).toBeGreaterThan(0);
    expect(rec.recording).toBe(false);
  });

  it('stops media tracks on stop (privacy guarantee)', async () => {
    const rec = new AudioRecorder();
    await rec.start();
    await rec.stop();
    expect(track.stop).toHaveBeenCalled();
  });

  it('ignores a second start while already recording', async () => {
    const rec = new AudioRecorder();
    await rec.start();
    await rec.start();
    expect(getUserMedia).toHaveBeenCalledTimes(1);
    expect(rec.recording).toBe(true);
  });
});
