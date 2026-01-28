#!/usr/bin/env python3
"""
Populate TVSHOW metadata (synopsis, image_url) from TVMaze for the series
already present in your database (tables: tvshow, tvshow_term), and
download images locally.

Usage:
  python scripts/fetch_tvmaze_metadata.py [--only-missing] [--sleep 0.2]
                                         [--db database/tvshow.db]
                                         [--img-dir static/images/tvshow_images]
"""

import sqlite3
import json
import time
import argparse
import re
import os
from urllib import request, parse

# -------------------
# ARGUMENTS
# -------------------
parser = argparse.ArgumentParser(description="Populate TVSHOW metadata from TVMaze and download images")
parser.add_argument("--only-missing", action="store_true", help="Update only rows missing synopsis or image")
parser.add_argument("--sleep", type=float, default=0.2, help="Sleep seconds between API calls")
parser.add_argument("--db", type=str, default=os.path.join('database', 'tvshow.db'), help="Path to SQLite database")
parser.add_argument("--img-dir", type=str, default=os.path.join('static','images','tvshow_images'), help="Folder to save images")
args = parser.parse_args()

DB_PATH = args.db
IMG_DIR = args.img_dir
os.makedirs(IMG_DIR, exist_ok=True)

# -------------------
# UTILITAIRES
# -------------------
def http_get_json(url: str, params: dict = None):
    """Get JSON from URL"""
    if params:
        q = parse.urlencode(params)
        sep = "&" if "?" in url else "?"
        url = f"{url}{sep}{q}"
    req = request.Request(url)
    with request.urlopen(req, timeout=30) as resp:
        if resp.status != 200:
            raise RuntimeError(f"HTTP {resp.status} for {url}")
        data = resp.read()
        return json.loads(data.decode("utf-8"))

def strip_tags(html: str) -> str:
    """Remove HTML tags"""
    if not html:
        return ""
    return re.sub(r"<[^>]+>", "", html).strip()

def download_image(url: str, path: str):
    """Download image from URL"""
    try:
        request.urlretrieve(url, path)
        return True
    except Exception as e:
        print(f"Failed to download image {url}: {e}")
        return False

# -------------------
# LOGIQUE
# -------------------
def main():
    if not os.path.exists(DB_PATH):
        print(f"Base de données introuvable: {DB_PATH}. Lancez d'abord l'init.")
        return

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    try:
        if args.only_missing:
            cur.execute(
                "SELECT id, name, synopsis, image_url FROM tvshow WHERE synopsis IS NULL OR synopsis='' OR image_url IS NULL OR image_url=''"
            )
        else:
            cur.execute("SELECT id, name, synopsis, image_url FROM tvshow")
        series = cur.fetchall()
        total = len(series)
        print(f"{total} séries à traiter")

        updated = 0
        skipped = 0

        for i, (serie_id, name, synopsis, image_url) in enumerate(series, 1):
            try:
                data = http_get_json("https://api.tvmaze.com/singlesearch/shows", params={"q": name})
            except Exception as e:
                print(f"[{i}/{total}] WARN: impossible de récupérer '{name}': {e}")
                skipped += 1
                continue

            summary_html = data.get("summary") or ""
            overview = strip_tags(summary_html)
            image_data = data.get("image") or {}
            image_url_new = image_data.get("original") or image_data.get("medium") or ""

            changed = False
            if overview and overview != (synopsis or ""):
                synopsis = overview
                changed = True
            if image_url_new and image_url_new != (image_url or ""):
                image_url = image_url_new
                changed = True

            # Téléchargement image locale
            if image_url:
                img_path = os.path.join(IMG_DIR, f"{serie_id}.jpg")
                if download_image(image_url, img_path):
                    print(f"[{i}/{total}] Image téléchargée: {img_path}")

            if changed:
                cur.execute("UPDATE tvshow SET synopsis=?, image_url=? WHERE id=?", (synopsis, image_url, serie_id))
                conn.commit()
                updated += 1
                print(f"[{i}/{total}] Updated: {name}")
            else:
                skipped += 1
                print(f"[{i}/{total}] No change: {name}")

            time.sleep(max(0.0, args.sleep))
    finally:
        conn.close()

    print(f"Fini. Mis à jour: {updated}, inchangé: {skipped}")


if __name__ == "__main__":
    main()

