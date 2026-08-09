"""One-shot inventory: download SSCAIT bots, attach BASIL ratings, list maps."""

import json
import logging
import re
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import requests
from scbw.bot_storage import SscaitBotStorage

SSCAIT_BOTS_URL = "https://sscaitournament.com/api/bots.php"
BASIL_DATA_CANDIDATES = [
    "https://data.basil-ladder.net/bots.json",
    "https://data.basil-ladder.net/ranking.json",
    "https://data.basil-ladder.net/latest/bots.json",
]
BASIL_BADGE_URL = "https://basil-badge-production.up.railway.app/badge/{name}"

SCBW_DIR = Path.home() / ".scbw"
MAP_DIR = SCBW_DIR / "maps"
BOT_DIR = SCBW_DIR / "bots"
OUTPUT_PATH = Path("inventory.json")
LOG_PATH = Path("inventory.log")

MAP_SUFFIXES = {".scm", ".scx"}
DOWNLOAD_WORKERS = 8
RATING_WORKERS = 16
MIN_AI_BYTES = 10_000

log = logging.getLogger("inventory")


def setup_logging():
    """Log to both inventory.log and the console."""
    logging.getLogger("scbw").setLevel(logging.CRITICAL)
    log.setLevel(logging.INFO)
    formatter = logging.Formatter("%(asctime)s  %(message)s", "%H:%M:%S")
    for handler in (logging.FileHandler(LOG_PATH, mode="w"), logging.StreamHandler()):
        handler.setFormatter(formatter)
        log.addHandler(handler)


def normalize(name):
    """Loose key for matching bot names across SSCAIT and BASIL."""
    return re.sub(r"[^a-z0-9]", "", name.lower())


# --------------------------------------------------------------------------- #
# Download                                                                     #
# --------------------------------------------------------------------------- #

def fetch_specs(url=SSCAIT_BOTS_URL, timeout=60):
    """Return the raw list of bot specs published on the SSCAIT server."""
    response = requests.get(url, timeout=timeout)
    response.raise_for_status()
    return [spec for spec in response.json() if spec.get("name")]


def download_all(specs, bot_dir=BOT_DIR, workers=DOWNLOAD_WORKERS):
    """Download every missing bot, skipping those already installed."""
    bot_dir.mkdir(parents=True, exist_ok=True)
    storage = SscaitBotStorage(str(bot_dir))

    pending = [s for s in specs if not (bot_dir / s["name"]).exists()]
    log.info(f"DOWNLOAD  {len(specs) - len(pending)} present, {len(pending)} to fetch")

    def fetch(spec):
        try:
            return spec["name"], storage.try_download(spec) is not None
        except Exception:
            return spec["name"], False

    with ThreadPoolExecutor(max_workers=workers) as pool:
        for i, (name, ok) in enumerate(pool.map(fetch, pending), 1):
            log.info(f"  {i}/{len(pending)}  {'ok  ' if ok else 'FAIL'}  {name}")


# --------------------------------------------------------------------------- #
# Local inventory                                                              #
# --------------------------------------------------------------------------- #

def read_installed(bot_dir=BOT_DIR):
    """Return [{name, race}] for bots whose files look complete."""
    bots = []
    for path in sorted(bot_dir.iterdir()):
        meta = path / "bot.json"
        ai_dir = path / "AI"
        if not meta.is_file() or not ai_dir.is_dir():
            log.info(f"  SKIP  {path.name} (missing bot.json or AI/)")
            continue
        payload = sum(f.stat().st_size for f in ai_dir.rglob("*") if f.is_file())
        if payload < MIN_AI_BYTES:
            log.info(f"  SKIP  {path.name} (AI/ holds only {payload} bytes)")
            continue
        try:
            data = json.loads(meta.read_text())
        except (json.JSONDecodeError, OSError):
            log.info(f"  SKIP  {path.name} (unreadable bot.json)")
            continue
        # The declared name is what scbw.play expects; it may differ from the dir
        bots.append({
            "name": data.get("name", path.name),
            "race": data.get("race", "Unknown").lower(),
        })
    return bots


# --------------------------------------------------------------------------- #
# Ratings                                                                      #
# --------------------------------------------------------------------------- #

def fetch_ratings_bulk(timeout=30):
    """Try the aggregated BASIL data files. Returns {normalized_name: elo}."""
    for url in BASIL_DATA_CANDIDATES:
        try:
            response = requests.get(url, timeout=timeout)
            response.raise_for_status()
            payload = response.json()
        except Exception:
            continue

        entries = payload if isinstance(payload, list) else payload.get("bots", [])
        ratings = {}
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            name = entry.get("name") or entry.get("botName")
            # Field naming varies between BASIL revisions
            elo = entry.get("rating", entry.get("elo", entry.get("mu")))
            if name and elo is not None:
                ratings[normalize(name)] = elo
        if ratings:
            log.info(f"  ratings from {url}: {len(ratings)} entries")
            return ratings
    return {}


def fetch_ratings_badges(names, workers=RATING_WORKERS, timeout=20):
    """Fall back to the per-bot BASIL badge endpoint, one request per bot."""
    def fetch(name):
        try:
            response = requests.get(BASIL_BADGE_URL.format(name=name), timeout=timeout)
            response.raise_for_status()
            # Shields.io endpoint format: {"label": ..., "message": "1696"}
            match = re.search(r"\d+", str(response.json().get("message", "")))
            return name, int(match.group()) if match else None
        except Exception:
            return name, None

    with ThreadPoolExecutor(max_workers=workers) as pool:
        return {normalize(n): e for n, e in pool.map(fetch, names) if e is not None}


def attach_ratings(bots):
    """Add an 'elo' key to each bot, None when BASIL has no rating for it."""
    names = [b["name"] for b in bots]

    ratings = fetch_ratings_bulk()
    if not ratings:
        log.info("  no aggregated file worked, falling back to per-bot badges")
        ratings = fetch_ratings_badges(names)

    for bot in bots:
        bot["elo"] = ratings.get(normalize(bot["name"]))

    rated = sum(1 for b in bots if b["elo"] is not None)
    log.info(f"RATINGS   {rated}/{len(bots)} bots matched to a BASIL rating")
    return bots


# --------------------------------------------------------------------------- #
# Maps                                                                         #
# --------------------------------------------------------------------------- #

def list_maps(map_dir=MAP_DIR):
    """Return map paths relative to the scbw map dir, e.g. 'sscai/(2)Benzene.scx'."""
    return sorted(
        str(path.relative_to(map_dir))
        for path in map_dir.rglob("*")
        if path.suffix.lower() in MAP_SUFFIXES
    )


# --------------------------------------------------------------------------- #

def main():
    setup_logging()

    download_all(fetch_specs())

    bots = attach_ratings(read_installed())
    bots.sort(key=lambda b: (-(b["elo"] or -1), b["name"]))
    maps = list_maps()

    OUTPUT_PATH.write_text(
        json.dumps({"bots": bots, "maps": maps}, indent=2, ensure_ascii=False)
    )

    races = Counter(b["race"] for b in bots)
    log.info(f"INVENTORY {len(bots)} bots  " + "  ".join(
        f"{r}={n}" for r, n in sorted(races.items())))
    log.info(f"{len(maps)} maps")
    log.info(f"written to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()