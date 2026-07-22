#!/usr/bin/env python3
"""
generate_data.py — emits data.json for the HK Weather (A & B) dashboard.

The dashboard shell (index.html) fetches ./data.json every 60s and renders it.
Fill in the collect_* functions below with your strategy's real source (DB query,
log parse, exchange/Polymarket API, ...), flip STATUS to "paper", then:

    python generate_data.py                                  # writes ./data.json
    git commit -am "data $(date -u +%FT%TZ)" && git push     # publish

Run as-is and it reproduces the current "awaiting first data push" state with a
real timestamp. Field-by-field schema is documented in README.md.
Any numeric field left as None renders as "—", so partial fills are safe.
"""

from __future__ import annotations
import json
from datetime import datetime, timezone
from pathlib import Path

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
STATUS     = "awaiting"          # "awaiting" -> amber banner. Flip to "paper" once wired.
SOURCE_BOX = "aws-dublin"
CURRENCY   = "USD"
OUT_PATH   = Path(__file__).with_name("data.json")


# ---------------------------------------------------------------------------
# Data collectors — replace the bodies with your real source
# ---------------------------------------------------------------------------
def collect_kpis() -> dict:
    # TODO: pull from your book / ledger.
    return {
        "book_equity":    None,   # e.g. 5124
        "start_equity":   None,   # e.g. 5000
        "realized_pnl":   None,   # signed; colours green/red
        "return_pct":     None,   # percent, e.g. 2.48
        "open_positions": None,   # int
        "closed_trades":  None,   # int
        "win_rate_pct":   None,   # 0..100
        "note":           None,   # short free text, e.g. "18/18 crossing days"
    }


def collect_equity_curve() -> dict:
    # TODO: (label, equity) points, oldest first.
    return {"labels": [], "values": []}


def collect_variants() -> list[dict]:
    # Per-variant A / B breakdown (rendered under "Per-variant").
    return [
        # {"name": "A (afternoon cross)", "trades": 11, "win_pct": 82, "pnl": 96, "pf": 2.4},
        # {"name": "B (morning fade)",    "trades": 7,  "win_pct": 57, "pnl": 28, "pf": 1.3},
    ]


def collect_open_positions() -> list[dict]:
    return [
        # {"market": "HK-high-≥33C 07-22", "side": "yes", "notional": "$120", "opened": "07-22 06:10"},
    ]


def collect_recent_trades(limit: int = 15) -> list[dict]:
    # Newest first, capped at `limit`.
    return [
        # {"time": "07-21 09:00", "market": "HK-high-≥33C", "side": "yes",
        #  "reason": "settle", "return_pct": 6.1, "pnl": 9},
    ]


def collect_recent_signals(limit: int = 15) -> list[dict]:
    # Newest first, capped at `limit`.
    return [
        # {"time": "07-22 05:00", "market": "HK-high-≥33C", "side": "yes", "detail": "cross @ 0.62"},
    ]


# ---------------------------------------------------------------------------
def build_payload() -> dict:
    return {
        "display_name":   "HK Weather — A & B",
        "status":         STATUS,
        "generated_utc":  datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "source_box":     SOURCE_BOX,
        "currency":       CURRENCY,
        "kpis":           collect_kpis(),
        "equity_curve":   collect_equity_curve(),
        "sleeves":        collect_variants(),
        "open_positions": collect_open_positions(),
        "recent_trades":  collect_recent_trades(),
        "recent_signals": collect_recent_signals(),
    }


def main() -> None:
    p = build_payload()
    OUT_PATH.write_text(json.dumps(p, indent=2, ensure_ascii=False) + "\n")
    print(f"wrote {OUT_PATH}  (status={p['status']}, generated={p['generated_utc']})")


if __name__ == "__main__":
    main()
