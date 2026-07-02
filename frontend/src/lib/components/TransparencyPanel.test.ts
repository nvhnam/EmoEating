import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/svelte';
import TransparencyPanel from './TransparencyPanel.svelte';

describe('TransparencyPanel', () => {
  it('shows zone label, emotion bars and nutrient targets together', () => {
    render(TransparencyPanel, {
      props: { zone: 'NEG_DEACTIVE', probs: { sad: 0.7, neutral: 0.3 } }
    });
    expect(screen.getByText(/Negative · Low-energy/)).toBeInTheDocument();
    expect(screen.getByText('70%')).toBeInTheDocument();
    expect(screen.getByText('Folate')).toBeInTheDocument();
  });
});
