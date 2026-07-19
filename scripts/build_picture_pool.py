"""Offline builder for the DTZ picture-description pool.

Searches Wikimedia Commons (no API key required) for freely licensed photos of
everyday scenes matching typical DTZ Sprechen Teil 2 themes, downloads a
1024px rendition of the best hit per scene into data/pictures/, and writes a
manifest (data/pictures.json) with scene tags and license attribution.

Run once and commit the results — the app serves pictures from the repo and
never calls Commons at runtime. Re-running refreshes/extends the pool.

Usage:
    python scripts/build_picture_pool.py
"""

import argparse
import json
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
PICTURES_DIR = DATA_DIR / "pictures"
MANIFEST_PATH = DATA_DIR / "pictures.json"

API = "https://commons.wikimedia.org/w/api.php"
USER_AGENT = "B1-letter-practice/0.1 (personal language-learning tool)"

# scene id → (Commons search query, German scene label shown to the learner)
SCENES = {
    "supermarkt": ("people shopping supermarket interior", "Einkaufen im Supermarkt"),
    "arzt": ("doctor patient consultation clinic", "Beim Arzt"),
    "spielplatz": ("children playing playground", "Auf dem Spielplatz"),
    "buero": ("office meeting colleagues discussion", "Bei der Arbeit im Büro"),
    "kueche": ("family cooking kitchen meal", "Kochen in der Küche"),
    "bahnhof": ("railway station platform passengers waiting", "Am Bahnhof"),
    "unterricht": ("adult education classroom students teacher", "Im Unterricht"),
    "restaurant": ("people eating restaurant table", "Im Restaurant"),
    "markt": ("vegetable market stall customers", "Auf dem Markt"),
    "park": ("family picnic park summer", "Im Park"),
    "umzug": ("moving house cardboard boxes apartment", "Beim Umzug"),
    "bushaltestelle": ("people waiting bus stop city", "An der Bushaltestelle"),
}


def api_get(params: dict) -> dict:
    query = urllib.parse.urlencode({**params, "format": "json"})
    request = urllib.request.Request(f"{API}?{query}", headers={"User-Agent": USER_AGENT})
    for attempt in range(5):
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                return json.load(response)
        except urllib.error.HTTPError as e:
            if e.code != 429 or attempt == 4:
                raise
            time.sleep(20 * (attempt + 1))


def search_scene(query: str) -> list[dict]:
    time.sleep(2)  # stay under the anonymous-API rate limit
    data = api_get({
        "action": "query",
        "generator": "search",
        "gsrsearch": f"filetype:bitmap {query}",
        "gsrnamespace": 6,
        "gsrlimit": 8,
        "prop": "imageinfo",
        "iiprop": "url|mime|extmetadata|size",
        "iiurlwidth": 1024,
    })
    pages = (data.get("query") or {}).get("pages") or {}
    hits = []
    for page in pages.values():
        info = (page.get("imageinfo") or [{}])[0]
        if info.get("mime") != "image/jpeg":
            continue
        if (info.get("width") or 0) < 800 or (info.get("height") or 0) < 500:
            continue
        meta = info.get("extmetadata") or {}
        hits.append({
            "title": page.get("title", ""),
            "index": page.get("index", 99),
            "thumburl": info.get("thumburl") or info.get("url"),
            "descriptionurl": info.get("descriptionurl", ""),
            "license": (meta.get("LicenseShortName") or {}).get("value", ""),
            "artist": (meta.get("Artist") or {}).get("value", ""),
        })
    return sorted(hits, key=lambda h: h["index"])


def download(url: str, dest: Path) -> None:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    for attempt in range(5):
        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                dest.write_bytes(response.read())
            return
        except urllib.error.HTTPError as e:
            if e.code != 429 or attempt == 4:
                raise
            time.sleep(8 * (attempt + 1))


def strip_html(text: str) -> str:
    import re

    return re.sub(r"<[^>]+>", "", text).strip()


def load_manifest() -> list[dict]:
    try:
        return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    except (FileNotFoundError, ValueError):
        return []


def save_entry(entry: dict) -> None:
    manifest = [e for e in load_manifest() if e["id"] != entry["id"]]
    manifest.append(entry)
    manifest.sort(key=lambda e: e["id"])
    MANIFEST_PATH.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def fetch_scene(scene_id: str, pick: int, query_override: str | None = None) -> bool:
    query, label = SCENES[scene_id]
    if query_override:
        query = query_override
    hits = search_scene(query)
    if len(hits) <= pick:
        print(f"  {scene_id}: no usable hit at index {pick}, skipped", file=sys.stderr)
        return False
    hit = hits[pick]
    filename = f"{scene_id}.jpg"
    download(hit["thumburl"], PICTURES_DIR / filename)
    save_entry({
        "id": scene_id,
        "file": filename,
        "scene": label,
        "source": hit["descriptionurl"],
        "license": hit["license"],
        "artist": strip_html(hit["artist"]),
    })
    print(f"  {scene_id}: [{pick}] {hit['title']} [{hit['license']}]")
    return True


def build(only_scene: str | None, pick: int, query: str | None) -> None:
    PICTURES_DIR.mkdir(parents=True, exist_ok=True)
    scene_ids = [only_scene] if only_scene else list(SCENES)
    for scene_id in scene_ids:
        fetch_scene(scene_id, pick, query_override=query)
    print(f"Manifest now has {len(load_manifest())} pictures ({MANIFEST_PATH})")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Build the DTZ picture pool.")
    parser.add_argument("--scene", help="refresh a single scene id only")
    parser.add_argument("--pick", type=int, default=0,
                        help="use the n-th search hit instead of the best match")
    parser.add_argument("--query", help="override the scene's search query (with --scene)")
    args = parser.parse_args()
    if args.query and not args.scene:
        parser.error("--query requires --scene")
    build(args.scene, args.pick, args.query)
