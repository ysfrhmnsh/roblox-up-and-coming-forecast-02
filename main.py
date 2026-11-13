#!/usr/bin/env python3
"""Forecast Roblox's Up-and-Coming top 10 for make.fun bounty
roblox-up-and-coming-forecast-01. v2 (see BUILD_NOTES.md).

Method: Monte Carlo rank simulation (deterministic, fixed seed).
Each game has a latent rank-value that mean-reverts toward a target
(extrapolated from its recent rank velocity) with band-dependent noise.
New games spawn at the bottom of the chart; a fraction are "risers"
that climb exponentially toward a top-10 target, matching the observed
riser trajectory (enter ~rank 55-88, reach top 10 within 24-48h).
Games age out 28 days after publishing (details.created when present,
else first-seen minus 3 days). The forecast is the time-averaged
marginal P(game at place k) over the scored window, per place, over
all games seen in the history; the residual mass is left unnamed so
brand-new games share it. Probabilities are honest and spread: the
log score punishes confident wrong calls far more than it rewards
confident right ones.

v2 changes vs v1 (each validated on BOTH practice splits):
- DRIFT_SHRINK 0.20 -> 0.15 (less velocity extrapolation; rank velocity
  is noisy on 4-11h archive gaps, and the final history's hourly reads
  make it finer still)
- RISER_LAM 0.09 -> 0.12 (risers climb faster, matching the observed
  riser path better)
- HORIZON 36 -> 24 (shorter target extrapolation)
- TOP_RISER_FRAC 0.25 -> 0.35 (more risers target places 1-2)
- N_SIMS 2000 -> 2500 (smoother probabilities; runtime still safe)

Stdlib only. Reads $MAKEFUN_INPUT_DIR (default /input), writes
$MAKEFUN_OUTPUT_DIR (default /output)/<task.output>.
"""
import json
import math
import os
import random
from datetime import datetime, timedelta

# ---- tuned parameters (backtested on the practice window + a Nov-4 split) ----
N_SIMS = 2500
SEED = 20261113
SIGMA_SCALE = 1.0       # scales band sigmas
DRIFT_SHRINK = 0.15     # regression slope of rank velocity on its next value
LAM = 0.05              # mean-reversion rate for ordinary games (/hour)
RISER_LAM = 0.12        # mean-reversion rate for risers (/hour)
RISER_FRAC = 0.45       # fraction of new spawns that are risers
TOP_RISER_FRAC = 0.35   # fraction of risers targeting places 1-2
SPAWN_RATE = 0.8        # brand-new games entering the chart per hour
HORIZON = 24.0          # hours to extrapolate rank velocity for targets
MAX_ROWS_PER_PLACE = 100
# per-hour rank-diffusion sd by rank band (measured on the archive)
SIGMA = {1: 0.82, 11: 2.10, 31: 3.32, 61: 3.85}


def parse_time(s):
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


def sigma_for(rank):
    for lo in (61, 31, 11, 1):
        if rank >= lo:
            return SIGMA[lo]
    return SIGMA[1]


def load_history(input_dir):
    snaps = []
    with open(os.path.join(input_dir, "history.ndjson")) as f:
        for line in f:
            line = line.strip()
            if line:
                snaps.append(json.loads(line))
    snaps.sort(key=lambda s: s["at"])
    task = json.load(open(os.path.join(input_dir, "task.json")))
    return snaps, task


def build_state(snaps):
    """Per-game state from the history."""
    times = [parse_time(s["at"]) for s in snaps]
    series = {}
    first_seen = {}
    created = {}
    for i, s in enumerate(snaps):
        for g in s.get("up_and_coming") or []:
            series.setdefault(g["universe_id"], []).append(
                (times[i], g["rank"]))
            first_seen.setdefault(g["universe_id"], times[i])
        det = s.get("details") or {}
        for k, v in det.items():
            if v and v.get("created"):
                created[int(k)] = parse_time(v["created"])
    last = {g["universe_id"] for g in snaps[-1].get("up_and_coming") or []}
    games = []
    for uid, obs in series.items():
        obs.sort()
        r_last = obs[-1][1]
        v = 0.0
        if len(obs) >= 2:
            (t1, r1), (t2, r2) = obs[-2], obs[-1]
            dt = (t2 - t1).total_seconds() / 3600.0
            if dt > 0:
                v = (r2 - r1) / dt
        ce = created.get(uid)
        if ce is None:
            ce = first_seen[uid] - timedelta(days=3)
        games.append({
            "uid": uid,
            "x": float(r_last),
            "v": v,
            "exit": ce + timedelta(days=28),
        })
    return games, times[-1], len(last)


def simulate(games, t0, n_chart, hours, rng):
    counts = {}
    anon_counts = [0] * 11
    total_slots = N_SIMS * hours

    def entry_rank():
        u = rng.random()
        if u < 0.5:
            return rng.uniform(80, 97)
        if u < 0.9:
            return rng.uniform(60, 80)
        return rng.uniform(35, 60)

    def riser_target():
        if rng.random() < TOP_RISER_FRAC:
            return rng.uniform(1, 2)
        return rng.uniform(3, 10)

    for _ in range(N_SIMS):
        pool = []
        for g in games:
            v = max(-1.5, min(1.5, g["v"] * DRIFT_SHRINK))
            if v < -0.5:
                target = max(1.0, g["x"] + v * 24.0)
                lam = RISER_LAM
            else:
                target = max(1.0, min(115.0, g["x"] + v * HORIZON))
                lam = LAM
            pool.append([g["x"], target, lam, g["uid"], g["exit"]])
        for h in range(hours):
            now = t0 + timedelta(hours=h + 1)
            # Poisson(spawn_rate) new games
            lam_p = math.exp(-SPAWN_RATE)
            k = 0
            p = 1.0
            while True:
                p *= rng.random()
                if p <= lam_p:
                    break
                k += 1
            for _ in range(k):
                er = entry_rank()
                if rng.random() < RISER_FRAC:
                    pool.append([er, riser_target(), RISER_LAM, None, None])
                else:
                    pool.append([er, rng.uniform(80, 100), LAM, None, None])
            alive = []
            for e in pool:
                if e[4] is not None and now >= e[4]:
                    continue
                sig = sigma_for(max(1, int(e[0]))) * SIGMA_SCALE
                e[0] += e[2] * (e[1] - e[0]) + rng.gauss(0, sig)
                alive.append(e)
            pool = alive
            pool.sort(key=lambda e: e[0])
            for place in range(1, 11):
                if place - 1 < len(pool):
                    uid = pool[place - 1][3]
                    if uid is None:
                        anon_counts[place] += 1
                    else:
                        c = counts.setdefault(uid, [0] * 11)
                        c[place] += 1
    probs = {}
    for uid, c in counts.items():
        for place in range(1, 11):
            p = c[place] / total_slots
            if p > 0:
                probs.setdefault(place, []).append((uid, p))
    unnamed = {place: anon_counts[place] / total_slots
               for place in range(1, 11)}
    return probs, unnamed


def build_forecast(probs, last_chart_uids):
    rows = []
    for place in range(1, 11):
        top = sorted(probs.get(place, []), key=lambda t: (-t[1], t[0]))
        for uid, p in top[:MAX_ROWS_PER_PLACE]:
            rows.append({"universe_id": uid, "place": place,
                         "p": round(p, 6)})
    # top10: greedy assignment maximising summed probability
    cand = []
    for place in range(1, 11):
        for uid, p in probs.get(place, []):
            cand.append((p, uid, place))
    cand.sort(key=lambda t: (-t[0], t[1], t[2]))
    used_g, used_p, top = set(), set(), {}
    for p, uid, place in cand:
        if uid in used_g or place in used_p:
            continue
        used_g.add(uid)
        used_p.add(place)
        top[place] = uid
        if len(top) == 10:
            break
    top10 = [top[k] for k in sorted(top)]
    if len(top10) < 10:  # fallback: fill from the last chart order
        for uid in last_chart_uids:
            if uid not in top10:
                top10.append(uid)
            if len(top10) == 10:
                break
    return {"probabilities": rows, "top10": top10[:10]}


def main():
    input_dir = os.environ.get("MAKEFUN_INPUT_DIR", "/input")
    output_dir = os.environ.get("MAKEFUN_OUTPUT_DIR", "/output")
    snaps, task = load_history(input_dir)
    window = task.get("window", {})
    hours = int(window.get("slots", 72))
    games, t0, n_chart = build_state(snaps)
    last_uids = [g["universe_id"]
                 for g in sorted(snaps[-1].get("up_and_coming") or [],
                                 key=lambda r: r["rank"])]
    rng = random.Random(SEED)
    probs, _unnamed = simulate(games, t0, n_chart, hours, rng)
    forecast = build_forecast(probs, last_uids)
    os.makedirs(output_dir, exist_ok=True)
    out_path = os.path.join(output_dir, task.get("output", "forecast.json"))
    with open(out_path, "w") as f:
        f.write(json.dumps(forecast) + "\n")


if __name__ == "__main__":
    main()
