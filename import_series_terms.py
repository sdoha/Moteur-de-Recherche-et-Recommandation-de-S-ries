#!/usr/bin/env python3
import os
from pathlib import Path
import sqlite3
import argparse

# -------------------
# ARGUMENTS
# -------------------
parser = argparse.ArgumentParser(description="Importer les fichiers clean dans la base SQLite")
parser.add_argument('--dir', type=str, required=False,
                    help="Chemin vers le dossier 'data_word_frequency_clean'")
parser.add_argument('--db', type=str, default=os.path.join('database', 'tvshow.db'),
                    help="Chemin vers le fichier SQLite")
args = parser.parse_args()

# -------------------
# CHEMINS
# -------------------
DATA_DIR = Path(args.dir) if args.dir else Path("data_word_frequency_clean")
DB_PATH = Path(args.db)

# -------------------
# FONCTION PRINCIPALE
# -------------------
def main():
    if not DATA_DIR.exists():
        print(f"Le dossier {DATA_DIR} n'existe pas ! Lancer depuis la racine du projet.")
        return

    if not DB_PATH.exists():
        print(f"Base de données introuvable: {DB_PATH}. Initialisez-la d'abord.")
        return

    # Connexion SQLite
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    # --- Ajouter les séries dans tvshow ---
    print("Ajout des séries dans TVShow...")
    tvshows = []
    for file_path in sorted(DATA_DIR.glob("*.txt")):
        serie_name = file_path.stem
        tvshows.append(serie_name)
        cur.execute("INSERT OR IGNORE INTO tvshow (name) VALUES (?)", (serie_name,))
    conn.commit()
    print(f"{len(tvshows)} séries ajoutées (ou déjà existantes).")

    # --- Ajouter les termes dans tvshow_term ---
    print("Ajout des termes dans TVShowTerm...")
    for serie_name in tvshows:
        cur.execute("SELECT id FROM tvshow WHERE name = ?", (serie_name,))
        row = cur.fetchone()
        if not row:
            continue
        serie_id = row[0]

        file_path = DATA_DIR / f"{serie_name}.txt"
        if not file_path.exists():
            continue

        with file_path.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if ":" not in line:
                    continue
                term, count_str = line.split(":", 1)
                term = term.strip()
                try:
                    count = float(count_str.strip())
                except ValueError:
                    continue
                cur.execute("""
                    INSERT OR IGNORE INTO tvshow_term (tvshow_id, term, count)
                    VALUES (?, ?, ?)
                """, (serie_id, term, count))
    conn.commit()
    conn.close()
    print("Import terminé !")

# -------------------
# LANCEMENT
# -------------------
if __name__ == "__main__":
    main()

