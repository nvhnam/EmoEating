# EmoEating

Voice-driven, emotion-conditioned food recommender. A short spoken utterance is
mapped to an affective zone (Russell's valence/arousal plane), each zone defines
a Nutritional Need Vector, and real-world foods are ranked by the
Emotion-Nutrition Matching Score (ENMS). Top meals are shown with images and
nearby restaurants.

Based on the UIST 2026 poster *EmoEating: Voice-Driven Food Recommendation via
Affect-to-Nutrient Mapping*.

## Repository layout

| Path | Contents |
|---|---|
| `paper/` | All paper-writing assets: `*.tex`, `emoeating_refs.bib`, `figures/`, `build.sh`, build output PDFs |
| `docs/` | Design specs for the application (`docs/superpowers/specs/`) |
| `backend/` | *(planned)* Python pipeline + FastAPI service |
| `frontend/` | *(planned)* SvelteKit + shadcn-svelte UI |

## Building the paper

```bash
cd paper
./build.sh          # build both main_v2.pdf and the v0→v2 diff
./build.sh v2       # build only main_v2
./build.sh diff     # build only the change-marked diff
```

Requires a TeX distribution with `pdflatex`, `bibtex`, and `latexdiff`.

## Application

The system design is specified in
[`docs/superpowers/specs/2026-06-26-emoeating-design.md`](docs/superpowers/specs/2026-06-26-emoeating-design.md).
Implementation has not started yet.
