"""Extract per-frame economy features from a saved Starcraft replay.

Runs the replay inside the starcraft:analyze Docker image (headful, under its
own Xvfb), lets the BWAPI dumper snapshot each player's economy at the requested
frames, and folds the result together with the match outcome from
play/metadata.csv into analyze/features/<replay>.json.

Usage:
  python analyze.py --replay play/parties/0a9c02acedea4d3b.rep --frames 100 200 300
"""

import argparse
import csv
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


def load_metadata():
    """Return {replay_name: {map, winner}} from play/metadata.csv."""
    out = {}
    with METADATA_PATH.open(newline="") as f:
        for row in csv.DictReader(f):
            winner = row["player_1"] if row["player_1_won"] == "True" else row["player_2"]
            out[row["replay"]] = {"map": row["map"], "winner": winner}
    return out


def run_replay(replay_path, frames, meta):
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
            "-v", f"{replay_path}:{CONTAINER_REPLAY_DIR / name}",
            "-e", f"REPLAY={name}",
            IMAGE,
        ]
        res = subprocess.run(cmd, capture_output=True, text=True)
        if res.returncode != 0:
            print(f"{name}: docker failed rc={res.returncode}:\n{res.stderr}")
            return None

        dump = tmp / "write" / "dump.jsonl"
        if not dump.is_file():
            print(f"{name}: no dump produced")
            return None

        sampled = []
        for line in dump.read_text().splitlines():
            obj = json.loads(line)
            if "frame" not in obj:
                continue
            sampled.append({
                "frame": obj["frame"],
                "players": {p["name"]: _features(p) for p in obj["players"]},
            })

    return {
        "map": meta["map"],
        "winner": meta["winner"],
        "frames": sampled,
    }


def _features(p):
    """Map a dumper player dict onto the compact per-frame feature shape."""
    return {
        "race": p["race"],
        "minerals": p["minerals"],
        "gas": p["gas"],
        "supply_used": p["supply_used"],
        "supply_total": p["supply_total"],
        "cum_minerals": p["cum_minerals"],
        "cum_gas": p["cum_gas"],
        "workers": p["workers"],
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--replay", action="append", required=True,
                        help="path to a .rep file (repeatable)")
    parser.add_argument("--frames", type=int, nargs="+", required=True,
                        help="target replay frames to sample, e.g. 100 200 300")
    parser.add_argument("--cpu", type=int, default=1,
                        help="number of replays to process in parallel")
    args = parser.parse_args()

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    WORK_DIR.mkdir(parents=True, exist_ok=True)
    meta = load_metadata()

    jobs = []
    for rep in args.replay:
        path = Path(rep).resolve()
        if not path.is_file():
            raise SystemExit(f"not a file: {rep}")
        if path.name not in meta:
            raise SystemExit(f"no metadata row for {path.name}")
        jobs.append((path, args.frames, meta[path.name]))

    with ThreadPoolExecutor(max_workers=max(1, args.cpu)) as pool:
        results = pool.map(lambda j: run_replay(*j), jobs)

    for (path, _, _), result in zip(jobs, results):
        if result is None:
            continue
        dest = OUT_DIR / path.name.replace(".rep", ".json")
        dest.write_text(json.dumps(result, indent=2) + "\n")
        print(f"wrote {dest}")


if __name__ == "__main__":
    main()
