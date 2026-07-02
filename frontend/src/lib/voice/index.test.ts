import { describe, it, expect, vi } from 'vitest';
import { createVoiceSession } from './index';
import { OpenAIRealtimeSession } from './openai';
import type { RealtimeToken } from '$lib/api';

const openaiToken: RealtimeToken = { provider: 'openai', client_secret: 'eph', model: 'm', voice: 'alloy' };

describe('createVoiceSession', () => {
  it('returns an OpenAIRealtimeSession for an openai token', () => {
    const s = createVoiceSession(openaiToken, { onAgentSpeaking: vi.fn() });
    expect(s).toBeInstanceOf(OpenAIRealtimeSession);
  });

  it('throws on an unknown provider instead of falling back to OpenAI (spec §6.4)', () => {
    const bogusToken = { ...openaiToken, provider: 'bogus' } as unknown as RealtimeToken;
    expect(() => createVoiceSession(bogusToken, { onAgentSpeaking: vi.fn() })).toThrow(
      /unknown voice provider: bogus/
    );
  });
});
