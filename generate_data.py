#!/usr/bin/env python3
"""
generate_data.py — emits data.json for the HK Weather (A & B) dashboard from the
live paper-trading record in hk_temp.db.

  Strategy A  = afternoon bucket-crossing pair   (SQLite table: positions / decisions)
  Strategy B  = morning rain NO-mode fade         (SQLite table: morning)

Run on the box that owns hk_temp.db, or pass --db:

    python generate_data.py                       # writes ./data.json
    python generate_data.py --stdout              # print JSON (for piping over ssh)
    python generate_data.py --db /path/hk_temp.db

If the DB isn't found it leaves data.json untouched (so a mis-scheduled run on a
box without the DB can't blank the dashboard). Schema is documented in README.md.

NOTE: the DB stores per-trade P&L, not a running bankroll, so the equity curve is
BOOK_BASE + cumulative realized P&L. Strategy-B $ P&L is derived as the recorded
per-share pnl × the recorded position size (no_exec_shares).
"""

from __future__ import annotations
import argparse, json, sqlite3, sys
from datetime import datetime, timezone
from pathlib import Path

BOOK_BASE   = 1000.0                 # nominal paper book (see note above)
SOURCE_BOX  = "aws-dublin"
CURRENCY    = "USD"
DEFAULT_DB  = Path.home() / "pm_crypto_trend" / "hk_temp" / "hk_temp.db"
OUT_PATH    = Path(__file__).with_name("data.json")


def _b_usd(r: dict):
    """Strategy-B dollar P&L = per-share pnl × recorded position size."""
    if r["pnl"] is None or r["no_exec_shares"] is None:
        return None
    return r["pnl"] * r["no_exec_shares"]


def build(db_path: Path) -> dict:
    c = sqlite3.connect(str(db_path)); c.row_factory = sqlite3.Row
    A = [dict(r) for r in c.execute("select * from positions order by ts")]
    B = [dict(r) for r in c.execute("select * from morning order by ts")]
    D = [dict(r) for r in c.execute("select * from decisions order by ts")]

    # --- Strategy A: crossing pairs ---
    a_res  = [r for r in A if r["resolved"]]
    a_open = [r for r in A if not r["resolved"]]
    a_pnl  = sum((r["pnl_usd"] or 0.0) for r in a_res)
    a_win  = sum(1 for r in a_res if (r["pnl_usd"] or 0.0) > 0)

    # --- Strategy B: morning rain NO-mode (only real trades, not no_rain skips) ---
    b_res  = [r for r in B if r["resolved"] and r["decision"] == "no_mode_paper"]
    b_usd  = {id(r): _b_usd(r) for r in b_res}
    b_pnl  = sum(v for v in b_usd.values() if v is not None)
    b_win  = sum(1 for v in b_usd.values() if v and v > 0)

    def pf(pairs):  # list of $ pnl -> profit factor
        wins = sum(v for v in pairs if v and v > 0)
        loss = sum(-v for v in pairs if v and v < 0)
        return round(wins / loss, 2) if loss > 0 else None

    variants = [
        {"name": "A · afternoon crossing", "trades": len(a_res),
         "win_pct": round(100 * a_win / len(a_res)) if a_res else 0,
         "pnl": round(a_pnl, 2), "pf": pf([(r["pnl_usd"] or 0.0) for r in a_res])},
        {"name": "B · morning rain (NO-mode)", "trades": len(b_res),
         "win_pct": round(100 * b_win / len(b_res)) if b_res else 0,
         "pnl": round(b_pnl, 2), "pf": pf(list(b_usd.values()))},
    ]

    # --- combined KPIs ---
    n_closed = len(a_res) + len(b_res)
    n_win    = a_win + b_win
    total    = a_pnl + b_pnl

    kpis = {
        "book_equity":    round(BOOK_BASE + total, 2),
        "start_equity":   BOOK_BASE,
        "realized_pnl":   round(total, 2),
        "return_pct":     round(100 * total / BOOK_BASE, 2),
        "open_positions": len(a_open),
        "closed_trades":  n_closed,
        "win_rate_pct":   round(100 * n_win / n_closed) if n_closed else 0,
        "note":           "A crossing + B rain · paper · nominal $1k book",
    }

    # --- equity curve: BOOK_BASE + cumulative realized P&L by settle date ---
    by_date: dict[str, float] = {}
    for r in a_res:
        by_date[r["date"]] = by_date.get(r["date"], 0.0) + (r["pnl_usd"] or 0.0)
    for r in b_res:
        by_date[r["date"]] = by_date.get(r["date"], 0.0) + (b_usd[id(r)] or 0.0)
    labels, values, cum = [], [], BOOK_BASE
    for d in sorted(by_date):
        cum += by_date[d]
        labels.append(d[5:])           # MM-DD
        values.append(round(cum, 2))

    # --- open positions ---
    open_positions = [{
        "market": f'HK {r["leg_b"]}+{r["leg_bplus"]} {r["date"][5:]}',
        "side":   "pair",
        "notional": f'${r["usd"]:.0f}',
        "opened": f'{r["date"][5:]} {r["tau"][:2]}:{r["tau"][2:]}',
    } for r in a_open]

    # --- recent closed trades (A + B), newest first ---
    trades = []
    for r in a_res:
        cost = r["usd"] or 0.0
        trades.append({"_ts": r["ts"], "time": r["date"][5:],
            "market": f'HK {r["leg_b"]}+{r["leg_bplus"]}', "side": "pair",
            "reason": f'resolved · {r["winner"]} won',
            "return_pct": round(100 * (r["pnl_usd"] or 0.0) / cost, 1) if cost else None,
            "pnl": round(r["pnl_usd"] or 0.0, 2)})
    for r in b_res:
        v = b_usd[id(r)]; hit = (r["winner"] == r["mode_bucket"])
        trades.append({"_ts": r["ts"], "time": r["date"][5:],
            "market": f'HK NO-mode {r["mode_bucket"]}', "side": "no",
            "reason": (f'lost · mode {r["mode_bucket"]}' if hit else f'won · {r["winner"]}'),
            "return_pct": round(100 * r["pnl"] / r["no_exec_cost"], 1) if r["no_exec_cost"] else None,
            "pnl": round(v, 2) if v is not None else None})
    trades.sort(key=lambda x: x["_ts"], reverse=True)
    for t in trades:
        t.pop("_ts")

    # --- recent signals: crossing decisions + morning no-rain, newest first ---
    signals = []
    for r in D:
        signals.append({"_ts": r["ts"], "time": r["date"][5:], "market": "A · crossing",
            "side": r["decision"].replace("skipped_depth", "skip"),
            "detail": r["detail"] or ""})
    for r in B:
        if r["decision"] == "no_rain":
            signals.append({"_ts": r["ts"], "time": r["date"][5:], "market": "B · rain",
                "side": "no-trade", "detail": f'no rain · mode {r["mode_bucket"]}'})
    signals.sort(key=lambda x: x["_ts"], reverse=True)
    for s in signals[:]:
        s.pop("_ts")

    return {
        "display_name":   "HK Weather — A & B",
        "status":         "paper",
        "generated_utc":  datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "source_box":     SOURCE_BOX,
        "currency":       CURRENCY,
        "kpis":           kpis,
        "equity_curve":   {"labels": labels, "values": values},
        "sleeves":        variants,
        "open_positions": open_positions,
        "recent_trades":  trades[:15],
        "recent_signals": signals[:12],
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default=str(DEFAULT_DB))
    ap.add_argument("--stdout", action="store_true", help="print JSON instead of writing data.json")
    a = ap.parse_args()
    if not Path(a.db).exists():
        print(f"[generate_data] DB not found at {a.db}; leaving data.json untouched", file=sys.stderr)
        sys.exit(0)
    payload = build(Path(a.db))
    text = json.dumps(payload, indent=2, ensure_ascii=False) + "\n"
    if a.stdout:
        sys.stdout.write(text)
    else:
        OUT_PATH.write_text(text)
        print(f"wrote {OUT_PATH}  (closed={payload['kpis']['closed_trades']}, "
              f"pnl={payload['kpis']['realized_pnl']}, gen={payload['generated_utc']})")


if __name__ == "__main__":
    main()
