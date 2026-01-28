#!/usr/bin/env python3
"""
Populate TVSHOW metadata (synopsis, image_url) from TMDb for the series
already present in your database (table: tvshow).

Usage:
  python scripts/fetch_tmdb_metadata.py --api-key <TMDB_API_KEY>
                                        [--only-missing]
                                        [--sleep 0.2]
                                        [--db database/tvshow.db]
"""

import sqlite3
import time
import argparse
import requests
import os

# -------------------
# ARGUMENTS
# -------------------
parser = argparse.ArgumentParser(description="Populate TVSHOW metadata from TMDb")
parser.add_argument("--api-key", type=str, required=True, help="TMDb API Key")
parser.add_argument("--only-missing", action="store_true", help="Update only rows missing synopsis or image")
parser.add_argument("--sleep", type=float, default=0.2, help="Sleep seconds between API calls")
parser.add_argument("--db", type=str, default=os.path.join('database','tvshow.db'), help="Path to SQLite database")
args = parser.parse_args()

DB_PATH = args.db
API_KEY = args.api_key

# -------------------
# CONSTANTES
# -------------------
TMDB_SEARCH_URL = "https://api.themoviedb.org/3/search/tv"
TMDB_IMAGE_BASE = "https://image.tmdb.org/t/p/original"
IMAGE_DIR = os.path.join("static","images","tvshow_images")
os.makedirs(IMAGE_DIR, exist_ok=True)

# -------------------
# FONCTIONS
# -------------------
def search_tmdb_tvshow(name: str):
    """Search TMDb TV show and return first result JSON"""
    params = {
        "api_key": API_KEY,
        "query": name,
        "language": "en-US"
    }
    resp = requests.get(TMDB_SEARCH_URL, params=params, timeout=30)
    if resp.status_code != 200:
        raise RuntimeError(f"HTTP {resp.status_code} for TMDb search: {name}")
    data = resp.json()
    results = data.get("results", [])
    return results[0] if results else None

# -------------------
# LOGIQUE PRINCIPALE
# -------------------
def main():
    if not os.path.exists(DB_PATH):
        print(f"Base de données introuvable: {DB_PATH}. Lancez d'abord l'init.")
        return

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    try:
        if args.only_missing:
            cur.execute("SELECT id, name, synopsis, image_url FROM tvshow WHERE synopsis IS NULL OR synopsis='' OR image_url IS NULL OR image_url='")
        else:
            cur.execute("SELECT id, name, synopsis, image_url FROM tvshow")
        series = cur.fetchall()
        total = len(series)
        print(f"{total} séries à traiter")

        updated = 0
        skipped = 0

        for i, (serie_id, name, synopsis, image_url) in enumerate(series, 1):
            try:
                tmdb_data = search_tmdb_tvshow(name)
            except Exception as e:
                print(f"[{i}/{total}] WARN: impossible de récupérer '{name}': {e}")
                skipped += 1
                continue

            if not tmdb_data:
                print(f"[{i}/{total}] Aucun résultat TMDb pour '{name}'")
                skipped += 1
                continue

            overview = tmdb_data.get("overview") or ""
            poster_path = tmdb_data.get("poster_path") or ""
            image_url_new = f"{TMDB_IMAGE_BASE}{poster_path}" if poster_path else ""

            # Mettre à jour synopsis et image_url si manquant
            changed = False
            if overview and not synopsis:
                synopsis = overview
                changed = True
            if image_url_new and not image_url:
                image_url = image_url_new
                changed = True

            if changed:
                cur.execute("UPDATE tvshow SET synopsis=?, image_url=? WHERE id=?", (synopsis, image_url, serie_id))
                conn.commit()
                updated += 1
                print(f"[{i}/{total}] Metadata mis à jour: {name}")
            else:
                print(f"[{i}/{total}] Metadata déjà présents: {name}")

            # Téléchargement poster local
            if image_url_new:
                safe_name = name.replace(' ', '_').replace('/', '_')
                filename = f"{serie_id}_{safe_name}.jpg"
                filepath = os.path.join(IMAGE_DIR, filename)
                if not os.path.exists(filepath):
                    try:
                        r = requests.get(image_url_new, timeout=30)
                        if r.status_code == 200:
                            with open(filepath, "wb") as f:
                                f.write(r.content)
                            print(f"[{i}/{total}] Poster téléchargé: {filepath}")
                    except Exception as e:
                        print(f"[{i}/{total}] Erreur téléchargement poster {name}: {e}")

            time.sleep(max(0.0, args.sleep))
    finally:
        conn.close()

    print(f"Fini. Metadata mis à jour: {updated}, inchangé/skipped: {skipped}")

if __name__ == "__main__":
    main()

