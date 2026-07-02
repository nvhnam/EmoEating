import { beforeEach, describe, expect, it, vi } from 'vitest';
import { render, screen } from '@testing-library/svelte';
import userEvent from '@testing-library/user-event';
import { get } from 'svelte/store';
import VoiceConsentDialog from './VoiceConsentDialog.svelte';
import { voiceConsentGiven } from '$lib/stores/session';

beforeEach(() => { voiceConsentGiven.set(false); });

describe('VoiceConsentDialog', () => {
  it('shows the accurate OpenAI disclosure (retention + we-do-not-store)', () => {
    render(VoiceConsentDialog, { props: { open: true, onAccept: vi.fn() } });
    expect(screen.getByText(/OpenAI/)).toBeInTheDocument();
    expect(screen.getByText(/short-term retention/i)).toBeInTheDocument();
    // must explicitly say WE do not store
    expect(screen.getByText(/we.*do not store/i)).toBeInTheDocument();
  });

  it('shows the clinical screening checkbox', () => {
    render(VoiceConsentDialog, { props: { open: true, onAccept: vi.fn() } });
    expect(screen.getByRole('checkbox')).toBeInTheDocument();
    expect(screen.getByText(/not a clinical tool/i)).toBeInTheDocument();
  });

  it('Accept button is disabled until screening checkbox is checked', async () => {
    const user = userEvent.setup();
    render(VoiceConsentDialog, { props: { open: true, onAccept: vi.fn() } });
    const btn = screen.getByRole('button', { name: /accept & continue/i });
    expect(btn).toBeDisabled();
    await user.click(screen.getByRole('checkbox'));
    expect(btn).not.toBeDisabled();
  });

  it('fires onAccept and sets voiceConsentGiven on accept with checkbox checked', async () => {
    const user = userEvent.setup();
    const onAccept = vi.fn();
    render(VoiceConsentDialog, { props: { open: true, onAccept } });
    await user.click(screen.getByRole('checkbox'));
    await user.click(screen.getByRole('button', { name: /accept & continue/i }));
    expect(onAccept).toHaveBeenCalledOnce();
    expect(get(voiceConsentGiven)).toBe(true);
  });

  it('fires onDecline from "Not now" without setting voiceConsentGiven', async () => {
    const user = userEvent.setup();
    const onDecline = vi.fn();
    render(VoiceConsentDialog, { props: { open: true, onAccept: vi.fn(), onDecline } });
    await user.click(screen.getByRole('button', { name: /not now/i }));
    expect(onDecline).toHaveBeenCalledOnce();
    expect(get(voiceConsentGiven)).toBe(false);
  });

  it('does NOT falsely claim the OpenAI leg is "not stored" or "never stored"', () => {
    // The accurate copy says OpenAI "may include short-term retention" —
    // it must NOT claim OpenAI data is never stored or not stored on OpenAI's side.
    render(VoiceConsentDialog, { props: { open: true, onAccept: vi.fn() } });
    // Matches e.g. "openai data is not stored" or "never stored" (false claims)
    expect(screen.queryByText(/openai[^.]*not stored|never stored/i)).toBeNull();
  });
});
