"""Extract per-frame economy features from saved Starcraft replays.

Runs each replay inside the starcraft:analyze Docker image (headful, under its
own Xvfb), lets the BWAPI dumper snapshot each player's economy at the requested
frames, and folds the result into analyze/features/<replay>.json.

The JSON is self-contained: players are described once (id/name/race) and each
frame holds an ordered `features` list aligned with the `players` list. The
`winner` field is the id (from that same list) of the winning player.

Usage:
  python analyze.py --replay ../play/parties --frames 100 200 300 --cpu 10
  python analyze.py --replay a.rep --replay b.rep --frames 100 200 300
"""

import argparse
import csv
import glob
import json
import subprocess
import tempfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parent
METADATA_PATH = ROOT.parent / "play" / "metadata.csv"
IMAGE = "starcraft:analyze"
OUT_DIR = ROOT / "features"
WORK_DIR = ROOT / ".work"

# Where the .rep is bind-mounted and expected inside the container.
CONTAINER_REPLAY_DIR = Path("/app/sc/maps/replays")

FEATURES_KEYS = ["minerals", "gas", "supply_used", "supply_total",
                 "cum_minerals", "cum_gas", "workers"]


def load_metadata():
    """Return {replay_name: {map, player_1, player_2, player_1_won}}."""
    out = {}
    with METADATA_PATH.open(newline="") as f:
        for row in csv.DictReader(f):
            out[row["replay"]] = row
    return out


def collect_replays(args):
    """Expand --replay paths (files, dirs, globs) into a sorted .rep list."""
    paths = set()
    for arg in args.replay:
        for match in glob.glob(arg):
            p = Path(match)
            if p.is_dir():
                paths.update(p.glob("*.rep"))
            elif p.is_file():
                paths.add(p)
    if not paths:
        raise SystemExit("no .rep file found")
    return sorted(paths, key=lambda p: p.name)


def extract_features(replay_path, frames, meta):
    """Extract features for one replay. Returns the feature dict, or None."""
    name = replay_path.name

    with tempfile.TemporaryDirectory(prefix=f"analyze-{name}-", dir=WORK_DIR) as tmp:
        tmp = Path(tmp)
        (tmp / "read").mkdir()
        (tmp / "write").mkdir()
        (tmp / "read" / "target_frames.txt").write_text(" ".join(map(str, frames)))

        cmd = [
            "docker", "run", "--rm",
            "-v", f"{tmp / 'read'}:/app/sc/bwapi-data/read",
            "-v", f"{tmp / 'write'}:/app/sc/bwapi-data/write",
            "-v", f"{replay_path.resolve()}:{CONTAINER_REPLAY_DIR / name}",
            "-e", f"REPLAY={name}",
            IMAGE,
        ]
        res = subprocess.run(cmd, capture_output=True, text=True)
        if res.returncode != 0:
            print(f"{name}: docker failed rc={res.returncode}: {res.stderr.strip()}")
            return None

        dump = tmp / "write" / "dump.jsonl"
        if not dump.is_file():
            print(f"{name}: no dump produced")
            return None

        players = None
        frames_out = []
        for line in dump.read_text().splitlines():
            obj = json.loads(line)
            if "frame" in obj:
                if players is None:
                    players = [{k: p[k] for k in ("id", "name", "race")}
                               for p in obj["players"]]
                frames_out.append({
                    "frame": obj["frame"],
                    "features": [_pick(p) for p in obj["players"]],
                })

    if players is None:
        print(f"{name}: no sampled frame in dump")
        return None

    winner_name = meta["player_1"] if meta["player_1_won"] == "True" else meta["player_2"]
    winner_id = next((p["id"] for p in players if p["name"] == winner_name), players[0]["id"])

    return {
        "map": meta["map"],
        "winner": winner_id,
        "players": players,
        "frames": frames_out,
    }


def _pick(p):
    return {k: p[k] for k in FEATURES_KEYS}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--replay", action="append", required=True,
                        help=".rep file, directory of .rep, or glob (repeatable)")
    parser.add_argument("--frames", type=int, nargs="+", required=True,
                        help="target replay frames to sample, e.g. 100 200 300")
    parser.add_argument("--cpu", type=int, default=1,
                        help="number of replays to process in parallel")
    args = parser.parse_args()

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    WORK_DIR.mkdir(parents=True, exist_ok=True)
    meta = load_metadata()

    jobs = []
    for path in collect_replays(args):
        if path.name not in meta:
            print(f"skip {path.name} (no metadata row)")
            continue
        jobs.append((path, args.frames, meta[path.name]))
    if not jobs:
        raise SystemExit("no replay has a metadata row")

    with ThreadPoolExecutor(max_workers=max(1, args.cpu)) as pool:
        results = pool.map(lambda j: extract_features(*j), jobs)

    for (path, _, _), result in zip(jobs, results):
        if result is None:
            continue
        dest = OUT_DIR / path.name.replace(".rep", ".json")
        dest.write_text(json.dumps(result, indent=2) + "\n")
        print(f"wrote {dest}")


if __name__ == "__main__":
    main()
