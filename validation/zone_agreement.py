"""
Zone Agreement Rate Analysis — guide.md Phase 7.2

Queries recommendation_sessions from MySQL and computes the zone agreement rate:
  X / N participants whose SER-detected zone matches their self-reported zone.

NEVER call this metric "accuracy". Frame as zone agreement rate throughout.

Per guide.md §7.2:
  "Report zone agreement rate (X/N participants whose detected zone matches
   their self-reported quadrant) — never call it accuracy."

Usage:
    python validation/zone_agreement.py [--env path/to/.env] [--out-json results.json]

Requires: 05_user_study_self_report.sql migration applied to the database,
          and self_reported_zone populated in recommendation_sessions rows.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from collections import defaultdict
from pathlib import Path

# ── DB access ──────────────────────────────────────────────────────────────────

def _fetch_study_sessions(db_conn=None) -> list[dict]:
    """
    Fetch sessions where BOTH detected zone AND self-reported zone are populated.
    Returns list of dicts with keys: session_id, detected_zone, self_reported_zone.
    """
    sys.path.insert(0, str(Path(__file__).parent.parent / "app"))

    if db_conn is None:
        from db.connection import get_connection
        db_conn = get_connection()
        close_after = True
    else:
        close_after = False

    from sqlalchemy import text

    sql = """
        SELECT id                AS session_id,
               detected_emotion  AS raw_detected,
               self_reported_zone
        FROM recommendation_sessions
        WHERE self_reported_zone IS NOT NULL
          AND detected_emotion   IS NOT NULL
          AND detected_emotion   != ''
        ORDER BY id
    """
    try:
        result = db_conn.execute(text(sql))
        rows = [dict(r._mapping) for r in result]
    finally:
        if close_after:
            db_conn.close()

    # Parse detected zone from "emotion|zone" or bare "emotion" format
    sessions = []
    for row in rows:
        raw = row["raw_detected"] or ""
        if "|" in raw:
            _emotion, detected_zone = raw.split("|", 1)
        else:
            # Legacy rows before zone tagging — skip (no zone to compare)
            continue
        sessions.append({
            "session_id":        row["session_id"],
            "detected_zone":     detected_zone.strip(),
            "self_reported_zone": row["self_reported_zone"].strip(),
        })
    return sessions


# ── Metrics ────────────────────────────────────────────────────────────────────

ALL_ZONES = ["Q1_POS_ACT", "Q2_NEG_ACT", "Q3_NEG_DEACT", "NEUTRAL_BASELINE"]


def _wilson_ci(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    """Wilson score confidence interval for a proportion k/n at z-score z."""
    if n == 0:
        return 0.0, 0.0
    p_hat = k / n
    centre  = p_hat + z**2 / (2 * n)
    spread  = z * math.sqrt(p_hat * (1 - p_hat) / n + z**2 / (4 * n**2))
    denom   = 1 + z**2 / n
    lo = max(0.0, (centre - spread) / denom)
    hi = min(1.0, (centre + spread) / denom)
    return round(lo, 4), round(hi, 4)


def compute_zone_agreement(sessions: list[dict]) -> dict:
    """
    Compute zone agreement rate and per-zone breakdown.

    Zone agreement rate = (sessions where detected_zone == self_reported_zone) / N
    95% Wilson CI reported for small pilot samples.
    """
    n = len(sessions)
    if n == 0:
        return {"error": "No sessions with self-reported zone found."}

    agreed = [s for s in sessions if s["detected_zone"] == s["self_reported_zone"]]
    k = len(agreed)
    rate = round(k / n, 4)
    ci_lo, ci_hi = _wilson_ci(k, n)

    # Per-zone breakdown
    by_zone: dict[str, dict] = {}
    for zone in ALL_ZONES:
        zone_sessions = [s for s in sessions if s["self_reported_zone"] == zone]
        zone_agreed   = [s for s in zone_sessions if s["detected_zone"] == zone]
        nz = len(zone_sessions)
        kz = len(zone_agreed)
        by_zone[zone] = {
            "n_self_reported": nz,
            "n_agreed":        kz,
            "agreement_rate":  round(kz / nz, 4) if nz > 0 else None,
            "ci_95":           _wilson_ci(kz, nz) if nz > 0 else None,
        }

    # Confusion-style cross-tab: self_reported_zone × detected_zone
    crosstab: dict[str, dict[str, int]] = {
        z: {p: 0 for p in ALL_ZONES} for z in ALL_ZONES
    }
    for s in sessions:
        sr = s["self_reported_zone"]
        dt = s["detected_zone"]
        if sr in crosstab and dt in crosstab.get(sr, {}):
            crosstab[sr][dt] += 1

    return {
        "n_sessions":         n,
        "n_agreed":           k,
        "zone_agreement_rate": rate,
        "ci_95_wilson":       (ci_lo, ci_hi),
        "by_zone":            by_zone,
        "crosstab":           crosstab,
    }


# ── Reporting ──────────────────────────────────────────────────────────────────

def _print_report(metrics: dict, out_json: str | None = None) -> None:
    if "error" in metrics:
        print(f"Error: {metrics['error']}")
        return

    col = 18
    print("\n" + "=" * 70)
    print("ZONE AGREEMENT RATE ANALYSIS  —  EmoEating UIST 2026 (guide.md §7.2)")
    print("=" * 70)
    n   = metrics["n_sessions"]
    k   = metrics["n_agreed"]
    r   = metrics["zone_agreement_rate"]
    lo, hi = metrics["ci_95_wilson"]
    print(f"Sessions analysed      : {n}")
    print(f"Zone agreement         : {k} / {n}  =  {r:.1%}")
    print(f"95% Wilson CI          : [{lo:.1%}, {hi:.1%}]")
    print()

    print(f"{'Zone (self-report)':<{col}}  {'N':>5}  {'Agreed':>7}  {'Rate':>8}  {'95% CI'}")
    print("-" * 60)
    for zone in ALL_ZONES:
        bz = metrics["by_zone"][zone]
        nz = bz["n_self_reported"]
        kz = bz["n_agreed"]
        rz = f"{bz['agreement_rate']:.1%}" if bz["agreement_rate"] is not None else "—"
        ci = bz["ci_95"]
        ci_str = f"[{ci[0]:.1%}, {ci[1]:.1%}]" if ci else "—"
        print(f"{zone:<{col}}  {nz:>5}  {kz:>7}  {rz:>8}  {ci_str}")

    print()
    print("Cross-tabulation (rows=self-reported, cols=SER-detected):")
    ct = metrics["crosstab"]
    header = " " * col + "".join(f"{z[:col]:>{col}}" for z in ALL_ZONES)
    print(header)
    for sr in ALL_ZONES:
        row = f"{sr:<{col}}" + "".join(f"{ct[sr][p]:>{col}}" for p in ALL_ZONES)
        print(row)

    print()
    print(
        "Honest limitations (guide.md §7.4):\n"
        "  • Self-report is an imperfect ground truth (future: EDA, HRV).\n"
        "  • Pilot N is small — frame as pilot evaluation throughout.\n"
        "  • NEUTRAL_BASELINE may be over-represented (catches low-confidence SER)."
    )

    if out_json:
        with open(out_json, "w", encoding="utf-8") as fh:
            json.dump(metrics, fh, indent=2, default=str)
        print(f"\nFull results written to: {out_json}")


# ── CLI entry point ────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Zone agreement rate analysis for EmoEating user study (guide.md §7.2)"
    )
    parser.add_argument(
        "--env", default=None,
        help="Path to .env file with DB credentials (default: auto-discover)",
    )
    parser.add_argument(
        "--out-json", default=None,
        help="Optional path to write JSON results",
    )
    args = parser.parse_args()

    if args.env:
        from dotenv import load_dotenv
        load_dotenv(args.env)

    print("Fetching user-study sessions from database...")
    try:
        sessions = _fetch_study_sessions()
    except Exception as exc:
        print(f"Database error: {exc}")
        print(
            "Ensure MySQL is running, .env credentials are set, and "
            "migration 05_user_study_self_report.sql has been applied."
        )
        sys.exit(1)

    print(f"Retrieved {len(sessions)} sessions with self-reported zone.")
    metrics = compute_zone_agreement(sessions)
    _print_report(metrics, args.out_json)


if __name__ == "__main__":
    main()
