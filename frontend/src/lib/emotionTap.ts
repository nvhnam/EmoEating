import { PUBLIC_API_BASE } from '$env/static/public';
import type { InferResult } from '$lib/api';

const BASE: string = PUBLIC_API_BASE ?? 'http://localhost:8000';

function toWsBase(httpBase: string): string {
  return httpBase.replace(/^http/, 'ws');
}

export interface TickEvent {
  confidence: number;
  elapsed: number;
}

export interface EmotionTapCallbacks {
  onTick?: (e: TickEvent) => void;
  onDone?: (infer: InferResult) => void;
  onSafetyFlag?: () => void;
}

type ServerMsg =
  | { type: 'tick'; confidence: number; elapsed: number }
  | { type: 'done'; infer: InferResult }
  | { type: 'safety_flag' };

export class EmotionTap {
  private ctx: AudioContext | null = null;
  private source: MediaStreamAudioSourceNode | null = null;
  private workletNode: AudioWorkletNode | null = null;
  private ws: WebSocket | null = null;
  private readonly callbacks: EmotionTapCallbacks;
  private pendingControl: object[] = [];

  constructor(callbacks: EmotionTapCallbacks) {
    this.callbacks = callbacks;
  }

  private _sendControl(obj: object): void {
    if (this.ws?.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify(obj));
    } else if (this.ws) {
      this.pendingControl.push(obj);
    }
  }

  async start(stream: MediaStream): Promise<void> {
    const Ctx: typeof AudioContext =
      window.AudioContext ??
      (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext;
    this.ctx = new Ctx();

    await this.ctx.audioWorklet.addModule('/emotion-worklet.js');
    this.workletNode = new AudioWorkletNode(this.ctx, 'emotion-processor');
    this.source = this.ctx.createMediaStreamSource(stream);
    this.source.connect(this.workletNode);
    // Connect to destination so the graph stays alive (output is silent)
    this.workletNode.connect(this.ctx.destination);

    this.workletNode.port.onmessage = (e: MessageEvent<ArrayBuffer>) => {
      if (this.ws?.readyState === WebSocket.OPEN) {
        this.ws.send(e.data);
      }
    };

    this.ws = new WebSocket(`${toWsBase(BASE)}/ws/emotion`);
    this.ws.binaryType = 'arraybuffer';
    this.ws.onopen = () => {
      const pending = this.pendingControl.splice(0);
      for (const msg of pending) {
        if (this.ws?.readyState === WebSocket.OPEN) {
          this.ws.send(JSON.stringify(msg));
        }
      }
    };
    this.ws.onmessage = (e: MessageEvent) => {
      if (typeof e.data !== 'string') return;
      let msg: ServerMsg;
      try {
        msg = JSON.parse(e.data) as ServerMsg;
      } catch {
        return;
      }
      if (msg.type === 'tick') {
        this.callbacks.onTick?.({ confidence: msg.confidence, elapsed: msg.elapsed });
      } else if (msg.type === 'done') {
        this.callbacks.onDone?.(msg.infer);
      } else if (msg.type === 'safety_flag') {
        this.callbacks.onSafetyFlag?.();
      }
    };
  }

  setAgentSpeaking(value: boolean): void {
    this._sendControl({ type: 'agent_speaking', value });
  }

  abort(): void {
    this._sendControl({ type: 'abort' });
    this.close();
  }

  close(): void {
    this.pendingControl = [];
    this.workletNode?.disconnect();
    this.source?.disconnect();
    void this.ctx?.close();
    this.ws?.close();
    this.ctx = null;
    this.source = null;
    this.workletNode = null;
    this.ws = null;
  }
}
