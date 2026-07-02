import type { RealtimeToken } from '$lib/api';
import type { VoiceSession, VoiceSessionCallbacks } from './types';
import { OpenAIRealtimeSession } from './openai';
import { GeminiLiveSession } from './gemini';

export function createVoiceSession(token: RealtimeToken, cbs: VoiceSessionCallbacks): VoiceSession {
  if (token.provider === 'openai') return new OpenAIRealtimeSession(token, cbs);
  if (token.provider === 'gemini') return new GeminiLiveSession(token, cbs);
  // Spec §6.4: an unknown provider must error loudly, never silently fall back to OpenAI.
  throw new Error(`unknown voice provider: ${token.provider}`);
}
