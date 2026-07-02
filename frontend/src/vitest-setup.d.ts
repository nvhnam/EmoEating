// Makes @testing-library/jest-dom matchers (e.g. toBeInTheDocument) visible to
// svelte-check. The runtime augmentation is loaded via vitest-setup.ts, but that
// root file is outside the check program's include, so we declare it here.
import '@testing-library/jest-dom/vitest';
