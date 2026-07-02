import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/svelte';
import NutrientTargets from './NutrientTargets.svelte';

describe('NutrientTargets', () => {
  it('lists zone priority micros without an NNV', () => {
    render(NutrientTargets, { props: { zone: 'NEG_DEACTIVE' } });
    expect(screen.getByText('Folate')).toBeInTheDocument();
    expect(screen.getByText('Omega-3')).toBeInTheDocument();
  });

  it('shows numeric targets when an NNV is supplied', () => {
    render(NutrientTargets, {
      props: {
        zone: 'POS_ACTIVE',
        nnv: {
          zone: 'POS_ACTIVE',
          macro_targets: { protein_g: 30, carb_g: 75, fat_g: 16.7 },
          macro_weights: { protein_g: 0.45, carb_g: 0.3, fat_g: 0.25 },
          micro_targets: { vit_c_mg: 30, vit_e_mg: 5 },
          priority_micros: ['vit_c_mg', 'vit_e_mg']
        }
      }
    });
    expect(screen.getByText('Protein')).toBeInTheDocument();
    expect(screen.getByText(/30 g/)).toBeInTheDocument();
    expect(screen.getByText('Vitamin C')).toBeInTheDocument();
  });

  it('appends the correct unit derived from the key suffix', () => {
    render(NutrientTargets, {
      props: {
        zone: 'NEG_DEACTIVE',
        nnv: {
          zone: 'NEG_DEACTIVE',
          macro_targets: { protein_g: 30 },
          macro_weights: { protein_g: 0.3, carb_g: 0.5, fat_g: 0.2 },
          micro_targets: { vit_c_mg: 30, vit_d_ug: 5, omega3_g: 0.5 },
          priority_micros: ['vit_c_mg', 'vit_d_ug', 'omega3_g']
        }
      }
    });
    expect(screen.getByText(/30 mg/)).toBeInTheDocument();
    expect(screen.getByText(/5 µg/)).toBeInTheDocument();
    expect(screen.getByText(/0\.5 g/)).toBeInTheDocument();
  });
});
