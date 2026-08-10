"""Sample and run random bot-vs-bot games, archiving replays and metadata."""

import argparse
import csv
import json
import random
import shutil
import subprocess
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Lock

import pandas as pd

ROOT = Path(__file__).resolve().parent
INVENTORY_PATH = ROOT.parent / "inventory" / "inventory.json"
REPLAY_DIR = ROOT / "parties"
METADATA_PATH = ROOT / "metadata.csv"
SCBW_GAME_DIR = Path.home() / ".scbw" / "games"

GAME_TIMEOUT_S = 1800
RACE_CODES = {"Z": "zerg", "T": "terran", "P": "protoss", "R": "random"}
METADATA_FIELDS = ["replay", "player_1", "player_2", "map", "player_1_won"]

_write_lock = Lock()


def load_inventory(path=INVENTORY_PATH):
    """Return the inventory bots as a DataFrame, plus the list of map paths."""
    inventory = json.loads(path.read_text())
    return pd.DataFrame(inventory["bots"]), inventory["maps"]


def filter_bots(bots, elo_min, elo_max):
    """Drop bots outside the Elo range. Unrated bots pass only if no bound is set."""
    if elo_min is None and elo_max is None:
        return bots
    keep = bots["elo"].notna()
    if elo_min is not None:
        keep &= bots["elo"] >= elo_min
    if elo_max is not None:
        keep &= bots["elo"] <= elo_max
    return bots[keep]


def race_pools(bots, races):
    """Split a two-letter matchup code into the two candidate bot pools."""
    if races is None:
        names = bots["name"].tolist()
        return names, names

    code = races.upper()
    if len(code) != 2 or any(c not in RACE_CODES for c in code):
        raise SystemExit(f"--races must be two letters from {''.join(RACE_CODES)}")

    pools = []
    for letter in code:
        race = RACE_CODES[letter]
        pool = bots.loc[bots["race"] == race, "name"].tolist()
        if not pool:
            raise SystemExit(f"no bot left for race '{race}' after filtering")
        pools.append(pool)
    return pools[0], pools[1]


def sample_jobs(pool_a, pool_b, maps, n, rng):
    """Draw n games with one bot from each pool, distinct, and a random map."""
    jobs = []
    for _ in range(n):
        a = rng.choice(pool_a)
        # Same-race matchups draw from one pool, so guard against self-play
        candidates = [b for b in pool_b if b != a]
        if not candidates:
            raise SystemExit("not enough distinct bots to build a matchup")
        jobs.append({
            "player_1": a,
            "player_2": rng.choice(candidates),
            "map": rng.choice(maps),
            "name": uuid.uuid4().hex[:16],
        })
    return jobs


def init_metadata():
    """Create the metadata file with its header if it does not exist yet."""
    REPLAY_DIR.mkdir(parents=True, exist_ok=True)
    if not METADATA_PATH.exists():
        with METADATA_PATH.open("w", newline="") as f:
            csv.DictWriter(f, METADATA_FIELDS).writeheader()


def archive(job, result):
    """Copy player 1's replay into parties/ and append one metadata row.

    Only player_0.rep is kept: both replays describe the same game, and player 1
    is the reference point for the outcome column.
    """
    game_dir = SCBW_GAME_DIR / f"GAME_{job['name']}"
    source = game_dir / "player_0.rep"
    if not source.is_file():
        return False

    replay_name = f"{job['name']}.rep"
    shutil.copy2(source, REPLAY_DIR / replay_name)

    row = {
        "replay": replay_name,
        "player_1": job["player_1"],
        "player_2": job["player_2"],
        "map": job["map"],
        "player_1_won": result["winner"] == job["player_1"],
    }
    with _write_lock:
        with METADATA_PATH.open("a", newline="") as f:
            csv.DictWriter(f, METADATA_FIELDS).writerow(row)
    return True


def read_result(game_name):
    """Return the sc-docker result dict, or None if the game is not usable.

    Crashes, timeouts and draws are discarded: their outcome carries no signal.
    """
    path = SCBW_GAME_DIR / f"GAME_{game_name}" / "result.json"
    if not path.is_file():
        return None
    try:
        result = json.loads(path.read_text())
    except (json.JSONDecodeError, OSError):
        return None
    if result.get("is_crashed") or result.get("is_realtime_outed"):
        return None
    if not result.get("winner"):
        return None
    return result


def run_game(job):
    """Play one game and archive it. Returns 'kept' or 'dropped'."""
    cmd = [
        "scbw.play",
        "--bots", job["player_1"], job["player_2"],
        "--map", job["map"],
        "--game_name", job["name"],
        "--headless",
        "--game_speed", "0",
        "--timeout", str(GAME_TIMEOUT_S),
        "--read_overwrite",
    ]
    try:
        subprocess.run(
            cmd, capture_output=True, text=True, timeout=GAME_TIMEOUT_S + 120
        )
    except subprocess.TimeoutExpired:
        return "dropped"

    result = read_result(job["name"])
    if result is None:
        return "dropped"
    return "kept" if archive(job, result) else "dropped"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--cpu", type=int, default=20, help="parallel games")
    parser.add_argument("--games", type=int, default=100, help="games to run")
    parser.add_argument("--seed", type=int, default=None, help="sampling seed")
    parser.add_argument("--races", default=None,
                        help="two-letter matchup, e.g. ZT for zerg vs terran")
    parser.add_argument("--elo-min", type=float, default=None, help="minimum Elo")
    parser.add_argument("--elo-max", type=float, default=None, help="maximum Elo")
    args = parser.parse_args()

    bots, maps = load_inventory()
    bots = filter_bots(bots, args.elo_min, args.elo_max)
    pool_a, pool_b = race_pools(bots, args.races)
    print(f"{len(pool_a)} vs {len(pool_b)} bots over {len(maps)} maps")

    init_metadata()
    rng = random.Random(args.seed)
    jobs = sample_jobs(pool_a, pool_b, maps, args.games, rng)

    counts = {"kept": 0, "dropped": 0}
    with ThreadPoolExecutor(max_workers=args.cpu) as pool:
        for i, status in enumerate(pool.map(run_game, jobs), 1):
            counts[status] += 1
            print(f"{i}/{args.games}  kept={counts['kept']} "
                  f"dropped={counts['dropped']}", end="\r", flush=True)
    print()


if __name__ == "__main__":
    main()