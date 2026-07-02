import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/svelte';
import EmotionBars from './EmotionBars.svelte';

describe('EmotionBars', () => {
  it('renders each emotion with a percentage, highest first', () => {
    render(EmotionBars, { props: { probs: { happy: 0.1, sad: 0.7, neutral: 0.2 } } });
    expect(screen.getByText(/sad/i)).toBeInTheDocument();
    expect(screen.getByText('70%')).toBeInTheDocument();
    const labels = screen.getAllByTestId('emotion-label').map((n) => n.textContent?.trim());
    expect(labels[0]).toMatch(/sad/i); // sorted descending
  });
});
