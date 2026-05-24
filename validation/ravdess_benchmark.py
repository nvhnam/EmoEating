"""
RAVDESS SER Benchmark — guide.md Phase 7.1

Runs emotion2vec_plus_large (off-the-shelf, no fine-tuning) on the RAVDESS
speech corpus and reports:
  - 4-zone confusion matrix
  - Per-zone precision / recall / F1
  - Macro-F1 (unweighted)

Frame as system-functional verification, NOT the headline contribution.

Usage:
    python validation/ravdess_benchmark.py --ravdess-dir path/to/RAVDESS_Speech_only

RAVDESS audio file naming convention:
    {Modality}-{VocalChannel}-{Emotion}-{Intensity}-{Statement}-{Repetition}-{Actor}.wav
    Emotion index (1-based): 01=neutral, 02=calm, 03=happy, 04=sad,
                             05=angry, 06=fearful, 07=disgust, 08=surprised
    Only Speech modality files (VocalChannel=01) are used for this benchmark.

Ground-truth zone mapping (research justification per Russell 1980):
  neutral  (01) → NEUTRAL_BASELINE  (low V, low A, near origin)
  calm     (02) → NEUTRAL_BASELINE  (Q4 passive-positive; merged per guide.md Phase 2)
  happy    (03) → Q1_POS_ACT        (+V, +A)
  sad      (04) → Q3_NEG_DEACT      (−V, −A)
  angry    (05) → Q2_NEG_ACT        (−V, +A)
  fearful  (06) → Q2_NEG_ACT        (−V, +A)
  disgust  (07) → Q2_NEG_ACT        (−V, mixed A; conventionally grouped with active negative)
  surprised(08) → Q1_POS_ACT        (high arousal; mapped consistent with SER_EMOTION_TO_ZONE)

Note on "surprised": Russell (1980) places surprise near the high-arousal boundary
between Q1 and Q2. We map it to Q1_POS_ACT to match the system's SER_EMOTION_TO_ZONE
constant, ensuring benchmark ground truth is consistent with what the system produces.
Any mismatch reported for "surprised" should be noted as an inherent ambiguity.

Reference:
  Livingstone, S. R., & Russo, F. A. (2018). The Ryerson Audio-Visual Database of
  Emotional Speech and Song (RAVDESS). PLOS ONE, 13(5), e0196391.
  DOI: 10.1371/journal.pone.0196391
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections import defaultdict
from pathlib import Path

# RAVDESS 1-based emotion code → 4-zone ground truth
RAVDESS_EMOTION_TO_ZONE: dict[int, str] = {
    1: "NEUTRAL_BASELINE",   # neutral
    2: "NEUTRAL_BASELINE",   # calm (Q4 → NEUTRAL per guide.md Phase 2)
    3: "Q1_POS_ACT",         # happy
    4: "Q3_NEG_DEACT",       # sad
    5: "Q2_NEG_ACT",         # angry
    6: "Q2_NEG_ACT",         # fearful
    7: "Q2_NEG_ACT",         # disgust
    8: "Q1_POS_ACT",         # surprised (see module docstring)
}

RAVDESS_EMOTION_NAMES: dict[int, str] = {
    1: "neutral", 2: "calm", 3: "happy", 4: "sad",
    5: "angry", 6: "fearful", 7: "disgust", 8: "surprised",
}

ALL_ZONES = ["Q1_POS_ACT", "Q2_NEG_ACT", "Q3_NEG_DEACT", "NEUTRAL_BASELINE"]


# ── File discovery ─────────────────────────────────────────────────────────────

def _parse_emotion_from_filename(wav_path: Path) -> int | None:
    """
    Parse the 1-based RAVDESS emotion code from a filename.
    Returns None if the file is not a speech-modality RAVDESS audio file.
    """
    parts = wav_path.stem.split("-")
    if len(parts) < 7:
        return None
    try:
        modality    = int(parts[0])   # 01=AV, 02=Audio-only, 03=Video-only
        vocal_chan  = int(parts[1])   # 01=Speech, 02=Song
        emotion_idx = int(parts[2])   # 01–08
    except ValueError:
        return None
    # Only Audio-only speech files; skip video-only and song
    if modality != 2 or vocal_chan != 1:
        return None
    return emotion_idx


def discover_ravdess_files(ravdess_dir: str) -> list[tuple[Path, str]]:
    """
    Walk `ravdess_dir` and return [(wav_path, ground_truth_zone), ...].
    Skips files that don't match the RAVDESS naming convention.
    """
    root = Path(ravdess_dir)
    pairs: list[tuple[Path, str]] = []
    for wav in root.rglob("*.wav"):
        emotion_idx = _parse_emotion_from_filename(wav)
        if emotion_idx is None:
            continue
        gt_zone = RAVDESS_EMOTION_TO_ZONE.get(emotion_idx)
        if gt_zone is None:
            continue
        pairs.append((wav, gt_zone))
    return sorted(pairs, key=lambda p: str(p[0]))


# ── Inference ──────────────────────────────────────────────────────────────────

def _run_inference_on_file(wav_path: Path) -> str | None:
    """
    Run emotion2vec_plus_large on one WAV file.
    Returns the predicted zone, or None on failure.
    """
    sys.path.insert(0, str(Path(__file__).parent.parent / "app"))
    try:
        from engine.ser_engine import predict_zone_from_audio
    except ImportError as exc:
        raise RuntimeError(
            f"SER engine import failed. Install funasr + modelscope: {exc}"
        ) from exc

    try:
        audio_bytes = wav_path.read_bytes()
        predicted_zone, _probs = predict_zone_from_audio(audio_bytes)
        return predicted_zone
    except Exception as exc:
        print(f"  [WARN] {wav_path.name}: {exc}", file=sys.stderr)
        return None


# ── Metrics ────────────────────────────────────────────────────────────────────

def _compute_metrics(
    results: list[tuple[str, str]],   # (ground_truth_zone, predicted_zone)
) -> dict:
    """
    Compute confusion matrix and per-zone precision/recall/F1 + macro-F1.
    """
    # Confusion matrix: cm[true][pred] = count
    cm: dict[str, dict[str, int]] = {z: {p: 0 for p in ALL_ZONES} for z in ALL_ZONES}
    for gt, pred in results:
        if gt in cm and pred in cm:
            cm[gt][pred] += 1

    per_zone: dict[str, dict] = {}
    f1_sum = 0.0
    for zone in ALL_ZONES:
        tp = cm[zone][zone]
        fp = sum(cm[other][zone] for other in ALL_ZONES if other != zone)
        fn = sum(cm[zone][other] for other in ALL_ZONES if other != zone)
        precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        recall    = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        f1        = (
            2 * precision * recall / (precision + recall)
            if (precision + recall) > 0 else 0.0
        )
        per_zone[zone] = {
            "tp": tp, "fp": fp, "fn": fn,
            "precision": round(precision, 4),
            "recall":    round(recall, 4),
            "f1":        round(f1, 4),
        }
        f1_sum += f1

    macro_f1 = round(f1_sum / len(ALL_ZONES), 4) if ALL_ZONES else 0.0
    total    = len(results)
    correct  = sum(1 for gt, pred in results if gt == pred)
    zone_acc = round(correct / total, 4) if total > 0 else 0.0

    return {
        "confusion_matrix": cm,
        "per_zone":         per_zone,
        "macro_f1":         macro_f1,
        "zone_accuracy":    zone_acc,
        "n_total":          total,
        "n_correct":        correct,
    }


# ── Reporting ──────────────────────────────────────────────────────────────────

def _print_report(metrics: dict, out_json: str | None = None) -> None:
    cm   = metrics["confusion_matrix"]
    pz   = metrics["per_zone"]
    col  = 18   # column width

    print("\n" + "=" * 70)
    print("RAVDESS SER BENCHMARK  —  MoodMeal UIST 2026 (guide.md §7.1)")
    print("Model: emotion2vec_plus_large (Ma et al., ACL 2024)")
    print("=" * 70)
    print(f"Files evaluated : {metrics['n_total']}")
    print(f"Correct (zone)  : {metrics['n_correct']}  ({metrics['zone_accuracy']:.1%})")
    print(f"Macro-F1        : {metrics['macro_f1']:.4f}")
    print()

    # Confusion matrix header
    print("Confusion matrix (rows=ground truth, cols=predicted):")
    header = " " * col + "".join(f"{z[:col]:>{col}}" for z in ALL_ZONES)
    print(header)
    for gt in ALL_ZONES:
        row = f"{gt:<{col}}" + "".join(f"{cm[gt][p]:>{col}}" for p in ALL_ZONES)
        print(row)

    print()
    print(f"{'Zone':<{col}} {'Prec':>8} {'Rec':>8} {'F1':>8}")
    print("-" * (col + 26))
    for zone in ALL_ZONES:
        z = pz[zone]
        print(f"{zone:<{col}} {z['precision']:>8.4f} {z['recall']:>8.4f} {z['f1']:>8.4f}")
    print("-" * (col + 26))
    print(f"{'Macro-F1':<{col}} {'':>8} {'':>8} {metrics['macro_f1']:>8.4f}")
    print()

    note = (
        "Note: 'calm' (RAVDESS emotion 2) is mapped to NEUTRAL_BASELINE "
        "(Q4 merged per guide.md Phase 2). 'surprised' is mapped to Q1_POS_ACT "
        "consistent with SER_EMOTION_TO_ZONE — see module docstring for discussion."
    )
    for line in [note[i:i+70] for i in range(0, len(note), 70)]:
        print(line)

    if out_json:
        with open(out_json, "w", encoding="utf-8") as fh:
            json.dump(metrics, fh, indent=2)
        print(f"\nFull results written to: {out_json}")


# ── CLI entry point ────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="RAVDESS SER benchmark for MoodMeal (guide.md Phase 7.1)"
    )
    parser.add_argument(
        "--ravdess-dir", required=True,
        help="Path to RAVDESS Speech_only directory (contains Actor_XX folders)",
    )
    parser.add_argument(
        "--out-json", default=None,
        help="Optional path to write full JSON results",
    )
    parser.add_argument(
        "--limit", type=int, default=None,
        help="Limit number of files (for quick smoke-test)",
    )
    args = parser.parse_args()

    print(f"Discovering RAVDESS audio files in: {args.ravdess_dir}")
    pairs = discover_ravdess_files(args.ravdess_dir)
    if not pairs:
        print("No matching RAVDESS files found. Check the directory path and file format.")
        sys.exit(1)

    if args.limit:
        pairs = pairs[: args.limit]
    print(f"Found {len(pairs)} speech audio files. Running SER inference...")

    results: list[tuple[str, str]] = []
    for i, (wav_path, gt_zone) in enumerate(pairs, 1):
        print(f"  [{i}/{len(pairs)}] {wav_path.name}", end=" ", flush=True)
        pred_zone = _run_inference_on_file(wav_path)
        if pred_zone is None:
            print("SKIP")
            continue
        results.append((gt_zone, pred_zone))
        status = "OK" if pred_zone == gt_zone else f"MISMATCH ({pred_zone})"
        print(status)

    if not results:
        print("No results to compute. All files were skipped.")
        sys.exit(1)

    metrics = _compute_metrics(results)
    _print_report(metrics, args.out_json)


if __name__ == "__main__":
    main()
