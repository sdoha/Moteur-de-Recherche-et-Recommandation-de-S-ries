#!/usr/bin/env python3
"""
Script pour extraire toutes les archives (.zip, .7z) dans un dossier principal
et tous ses sous-dossiers, récursivement, jusqu'à ce qu'il ne reste que les
fichiers de sous-titres (.srt, .sub).

Usage:
    python extract_all_subtitles.py --data-dir /chemin/vers/dossier
"""

import os
import sys
import zipfile
import logging
import argparse
from pathlib import Path

try:
    import py7zr
    SEVENZ_AVAILABLE = True
except ImportError:
    SEVENZ_AVAILABLE = False
    print("Warning: py7zr non disponible. Les fichiers 7Z seront ignorés.")

# Logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.FileHandler('extraction_recursive.log'), logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

ARCHIVE_EXTENSIONS = {'.zip', '.7z'}
SUBTITLE_EXTENSIONS = {'.srt', '.sub'}

def extract_zip(archive_path: Path, extract_to: Path) -> bool:
    try:
        with zipfile.ZipFile(archive_path, 'r') as zip_ref:
            zip_ref.extractall(extract_to)
        return True
    except Exception as e:
        logger.error(f"Échec extraction ZIP {archive_path}: {e}")
        return False

def extract_7z(archive_path: Path, extract_to: Path) -> bool:
    if not SEVENZ_AVAILABLE:
        logger.error(f"7Z non supporté (py7zr manquant): {archive_path}")
        return False
    try:
        with py7zr.SevenZipFile(archive_path, mode='r') as z:
            z.extractall(extract_to)
        return True
    except Exception as e:
        logger.error(f"Échec extraction 7Z {archive_path}: {e}")
        return False

# Liste des fichiers connus corrompus
CORRUPT_FILES = {
    "bionicwomans01VF.zip",
    "bionicwomans01VO.zip",
    "blades01VF.zip",
    "prisonbreaks01VO.zip",
    "xfiless01VF.zip",
    "xfiless03VF.zip"
}

def extract_archive(archive_path: Path) -> bool:
    if archive_path.name in CORRUPT_FILES:
        logger.info(f"Fichier corrompu détecté, ignoré : {archive_path.name}")
        return False
    # sinon on continue normalement
    extension = archive_path.suffix.lower()
    extract_to = archive_path.parent
    logger.info(f"Extraction {archive_path.name} vers {extract_to}")
    if extension == '.zip':
        return extract_zip(archive_path, extract_to)
    elif extension == '.7z':
        return extract_7z(archive_path, extract_to)
    else:
        logger.warning(f"Format non supporté: {extension}")
        return False

def recursive_extract(data_dir: Path):
    """Extrait toutes les archives dans data_dir récursivement jusqu'à ce qu'il n'en reste plus."""
    while True:
        archives = [p for p in data_dir.rglob("*") if p.suffix.lower() in ARCHIVE_EXTENSIONS]
        if not archives:
            break  # Plus aucune archive à extraire

        for archive_path in archives:
            if extract_archive(archive_path):
                archive_path.unlink()  # Supprime l'archive après extraction

def clean_only_subtitles(data_dir: Path):
    """Supprime tous les fichiers qui ne sont pas des sous-titres (.srt ou .sub)."""
    for f in data_dir.rglob("*"):
        if f.is_file() and f.suffix.lower() not in SUBTITLE_EXTENSIONS:
            f.unlink()

def main():
    parser = argparse.ArgumentParser(description="Extraction récursive des sous-titres")
    parser.add_argument('--data-dir', type=str, required=True, help='Dossier principal contenant les séries')
    args = parser.parse_args()

    data_dir = Path(args.data_dir)
    if not data_dir.exists():
        logger.error(f"Dossier non trouvé: {data_dir}")
        sys.exit(1)

    logger.info(f"Début de l'extraction récursive depuis : {data_dir}")
    recursive_extract(data_dir)
    logger.info("Extraction terminée. Nettoyage des fichiers inutiles...")
    clean_only_subtitles(data_dir)
    logger.info("Nettoyage terminé. Il ne reste plus que les fichiers .srt et .sub.")

if __name__ == "__main__":
    main()
