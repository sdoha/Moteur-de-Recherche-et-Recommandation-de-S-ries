#!/usr/bin/env python3
"""
Reset TVSHOW metadata and fetch everything again from TVMaze.
"""

import sqlite3
import json
import time
import os
from urllib import request, parse
import re

# Project-relative paths
DB_PATH = os.path.join("database", "tvshow.db")
IMG_DIR = os.path.join("static", "images", "tvshow_images")
os.makedirs(IMG_DIR, exist_ok=True)
SLEEP_SEC = 0.2

def http_get_json(url: str, params: dict = None):
    if params:
        q = parse.urlencode(params)
        sep = "&" if "?" in url else "?"
        url = f"{url}{sep}{q}"
    req = request.Request(url)
    with request.urlopen(req, timeout=30) as resp:
        if resp.status != 200:
            raise RuntimeError(f"HTTP {resp.status} for {url}")
        return json.loads(resp.read().decode("utf-8"))

def strip_tags(html: str) -> str:
    if not html:
        return ""
    return re.sub(r"<[^>]+>", "", html).strip()

def download_image(url: str, path: str):
    try:
        request.urlretrieve(url, path)
        return True
    except Exception as e:
        print(f"Failed to download image {url}: {e}")
        return False

def main():
    if not os.path.exists(DB_PATH):
        print(f"Base de données introuvable: {DB_PATH}. Lancez d'abord l'init.")
        return

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    # Optionnel : vider synopsis et image_url pour forcer le fetch
    cur.execute("UPDATE tvshow SET synopsis=NULL, image_url=NULL")
    conn.commit()
    print("Réinitialisation des synopsis et images OK")

    cur.execute("SELECT id, name FROM tvshow")
    series = cur.fetchall()
    total = len(series)
    print(f"{total} séries à traiter")

    for i, (serie_id, name) in enumerate(series, 1):
        try:
            data = http_get_json("https://api.tvmaze.com/singlesearch/shows", params={"q": name})
        except Exception as e:
            print(f"[{i}/{total}] WARN: impossible de récupérer '{name}': {e}")
            continue

        synopsis = strip_tags(data.get("summary") or "")
        image_data = data.get("image") or {}
        image_url = image_data.get("original") or image_data.get("medium") or ""

        # Télécharger image localement
        img_path = os.path.join(IMG_DIR, f"{serie_id}.jpg")
        if image_url and download_image(image_url, img_path):
            print(f"[{i}/{total}] Image téléchargée: {img_path}")

        # Mettre à jour la base
        cur.execute("UPDATE tvshow SET synopsis=?, image_url=? WHERE id=?", (synopsis, image_url, serie_id))
        conn.commit()
        print(f"[{i}/{total}] Mis à jour: {name}")

        time.sleep(SLEEP_SEC)

    conn.close()
    print("Mise à jour terminée pour toutes les séries.")

if __name__ == "__main__":
    main()

