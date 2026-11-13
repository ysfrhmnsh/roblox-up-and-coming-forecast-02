# Roblox Up-and-Coming Forecast — v2 BUILD NOTES

Bounty: make.fun `roblox-up-and-coming-forecast-01` ($500 USDC; entries close
2026-11-13 06:00 UTC). Entry is `main.py` in this directory. Build + test only —
no repo created, nothing submitted, no accounts/keypairs.

## Result (two practice splits, scored locally with the exact RULES scorer)

Apples-to-apples: the real `main.py` of each version, same scorer, same data.

| Forecast | Practice (10 reads, Nov 8–10) | Nov-4 split (11 reads, Nov 4–7) |
|---|---|---|
| House baseline (persistence) | **−43.512039** | −48.63 |
| v1 (submitted 04:29 WIB) | **−33.871227** | **−38.263753** |
| **v2 (this entry)** | **−33.542070** | **−37.884324** |

**v2 beats v1 on BOTH splits: +0.33 practice, +0.38 Nov-4.** (The Nov-4 v1
figure here is the real v1 main.py on the same harness; the earlier −38.31
was the sim3 prototype at 400 sims.)

## v2 changes vs v1 (each validated on both splits)

Tuned by single-factor grid (500 sims) then combination testing (1500 sims),
all on both splits; only changes that improved BOTH splits (or the average
without hurting either) were kept:

- **DRIFT_SHRINK 0.20 → 0.15** — less velocity extrapolation. Rank velocity
  from the last two observations is noisy on 4–11h archive gaps (0.3 was much
  worse, 0.10 alone was no better than the combination). The final history's
  hourly house reads make velocity finer still.
- **RISER_LAM 0.09 → 0.12** — risers climb faster, matching the observed
  riser path (enter ~rank 55, 28 at +12h, 13 at +24h, 9 at +48h) better.
- **HORIZON 36 → 24** — shorter target extrapolation (48 was much worse).
- **TOP_RISER_FRAC 0.25 → 0.35** — more risers target places 1–2.
- **N_SIMS 2000 → 2500** — smoother probabilities; runtime still safe
  (~59s practice input, ~48s split-2 input; limit 300s).

Rejected in tuning (worse on at least one split, or much worse): sigma
±15%, drift 0.3, riser_frac 0.35/0.55, riser_lam 0.07, spawn 0.6, horizon 48,
top_riser 0.2, velocity from a 3- or 4-observation least-squares fit (much
worse: −35.09/−40.43 — the last-two-observations velocity is the right one
on sparse archive gaps), climber thresholds −0.3/−0.7 (marginal), and
post-processing on top of the winning combination: probability tempering
(gamma 0.9/1.1/1.25/1.5 — 0.9 a wash, sharper gammas worse on Nov-4) and
per-place unnamed floors (no effect — the sim's unnamed share already
exceeds them). Plain combination A is the entry; no tempering, no floor.

## Approach — Monte Carlo rank simulation (`main.py`, stdlib only)

Same structure as v1 (see v1 BUILD_NOTES.md for the data findings):

- **Target** = last rank + shrunk recent rank velocity × horizon (velocity
  shrunk ×0.15). Games climbing fast (velocity < −0.5/h) get riser dynamics:
  target = rank + velocity × 24h, faster reversion.
- **Noise σ/hour by rank band** (measured on the archive): top 10: 0.82,
  11–30: 2.10, 31–60: 3.32, 61+: 3.85.
- **New games** spawn at the bottom (Poisson 0.8/hour, entry rank ~60–97);
  45% are "risers" climbing exponentially toward a top-10 target
  (35% of risers target places 1–2, rest 3–10; reversion 0.12/h).
- **Aging-out**: games leave 28 days after publishing (`details.created` when
  present, else first-seen minus 3 days).
- 2,500 simulations × 72 hours; forecast = time-averaged marginal
  P(game at place k). Residual mass is left **unnamed** so brand-new games
  share it — the log score punishes confident wrong calls far more than it
  rewards confident right ones.
- `top10` = greedy max-probability assignment (each game/place used once).

## Validation data (reconstructed, then verified)

The v1 work scripts read `/tmp/archive_timeline.jsonl`, which was lost when
/tmp was cleared. It was rebuilt from the public source named in the kit's
NOTICE.txt — https://github.com/Kenny-Dhub/roblox-snapshots — by converting
each snapshot commit's `data/discover/latest.json` (up-and-coming chart only)
into the kit snapshot shape. The rebuild was verified three ways:

1. Its first 34 reads are **identical** to the kit's `history.ndjson`
   (same timestamps, same ranks, same universe_ids, 0 mismatches).
2. The house baseline scores **−43.512039** on it — exact to 6 decimals
   against the RULES sheet, so the scorer + data are validated.
3. The v1 `main.py` reproduces **−33.871227** (practice) and **−38.31**
   (Nov-4 split, sim3 prototype) on it.

The rebuilt file is kept at `~/workspace/makefun/roblox-work/archive_timeline.jsonl`
(45 reads, 2026-10-30 → 2026-11-10T23:23Z) and the tuning scripts at
`~/workspace/makefun/roblox-work/` (`simv2.py`, `v2tune.py`, `v2stage2.py`,
`v2tune2.py`, `split_test.py`, `scorer.py`).

## Honest caveat

The live leaderboard's rank-1 entry ("Fitted practice table +
self-calibrating stack forecaster") scores **−13.18** on the dev phase
against our v1's −34.09 — a fitted occupancy-table + stacking approach,
not Monte Carlo. That gap was NOT closed here: v2 is a real, verified
improvement over v1 on both splits (+0.33/+0.38), but it is still in the
−33s, far from −13. A fitted-table/stack rebuild was out of reach in the
remaining time before the 13:00 WIB deadline, so this entry is the honest
Monte Carlo improvement, not a top-1 contender.

## Verification of `main.py` (this entry)

- Two runs on the kit practice input: **byte-identical output**
  (deterministic, fixed seed).
- Runtime ~59s per run on the practice input (limit 300s); ~48s on the
  smaller split-2 input. Final-history runtime estimate: the final history
  has ~100 snapshots and ~400 distinct games (vs 34/207 practice), so
  ~2× the practice runtime ≈ 120s — inside the limit.
- Output size within the 1,048,576-byte limit; exactly two keys
  (`probabilities`, `top10`); per-place sums ≤ 1; all p in (0, 1).
- Reads window/slots/output name from `task.json` (not hardcoded); handles
  both archive snapshots (no `details`) and house-recorder snapshots
  (hourly, with `details.created`).

## Files (submit dir)

- `main.py` — the entry (Python 3.13, stdlib only).
- `LICENSE` — MIT, SPDX identifier on the first line.
- `README.md` — this entry, one paragraph.
- `BUILD_NOTES.md` — this file.
- `.makefun/owner.json` — `{"wallet": "Hfc5L5xTTEjZQ55J1xT2cKK7kLLD6s4d2FZQC7TnnNU"}`.
