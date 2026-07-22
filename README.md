# HK Weather — A & B · dashboard

Read-only paper-trading dashboard for the **Hong Kong daily-temperature** Polymarket strategy
(variants A and B). Live at **https://rexlau-prog.github.io/hk-weather-dashboard/**.

The page (`index.html`) is a fixed shell. It fetches **`data.json`** from this repo every 60 s and
renders it. To update the dashboard, the box running the strategy just overwrites `data.json` and
pushes — **no HTML regeneration needed**.

Part of the strategy hub: **https://rexlau-prog.github.io/**

## `data.json` contract

```jsonc
{
  "display_name": "HK Weather — A & B",
  "status": "paper",                 // "awaiting" | "paper" | "live" | "archived"
  "generated_utc": "2026-07-22T14:00:00Z",   // ISO-8601; null => "awaiting" state
  "source_box": "aws-dublin",
  "currency": "USD",

  "kpis": {
    "book_equity":   30000,          // number | null  (null renders as "—")
    "start_equity":  30000,
    "realized_pnl":  0,              // signed; colours green/red
    "return_pct":    0.0,            // percent, e.g. 1.5 = +1.50%
    "open_positions": 0,             // integer count
    "closed_trades":  0,
    "win_rate_pct":   0,             // 0–100
    "note": ""                       // short free-text shown in the last KPI tile
  },

  "equity_curve": {
    "labels": ["07-22 04:00", "07-22 05:00"],   // x-axis labels
    "values": [30000, 30012]                     // book equity at each label
  },

  "sleeves": [                       // per-variant breakdown (A / B)
    { "name": "A", "trades": 0, "win_pct": 0, "pnl": 0, "pf": 0 }
  ],

  "open_positions": [                // { market, side, notional, opened }
    { "market": "HK-high-≥33C 07-22", "side": "yes", "notional": "$120", "opened": "07-22 06:10" }
  ],

  "recent_trades": [                 // { time, market, side, reason, return_pct, pnl }
    { "time": "07-22 09:00", "market": "HK-high-≥33C", "side": "yes", "reason": "settle", "return_pct": 4.2, "pnl": 5 }
  ],

  "recent_signals": [                // { time, market, side, detail }
    { "time": "07-22 05:00", "market": "HK-high-≥33C", "side": "yes", "detail": "cross @ 0.62" }
  ]
}
```

### Notes
- Any numeric field set to `null` (or omitted) renders as `—`, so partial pushes are safe.
- `notional` is a preformatted string (include the currency symbol) — the shell prints it verbatim.
- Keep `recent_trades` / `recent_signals` to the latest ~15 rows; the box decides the window.
- Set `status: "awaiting"` (or leave `generated_utc` null) to show the amber "awaiting data" banner.

### Suggested push (from the strategy box)

```bash
python generate_data.py > data.json     # your generator emits the JSON above
git commit -am "data $(date -u +%FT%TZ)" && git push
```
