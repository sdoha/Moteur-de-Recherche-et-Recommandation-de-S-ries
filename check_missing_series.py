from pathlib import Path

# Chemin vers le dossier qui contient les 128 séries
data_dir = Path(r"C:\Users\mouat\OneDrive\Bureau\S5C01\sous-titres")

missing_series = []

for series_dir in data_dir.iterdir():
    if series_dir.is_dir():
        # Cherche les fichiers .srt et .sub
        subtitle_files = list(series_dir.glob("*.srt")) + list(series_dir.glob("*.sub"))
        if not subtitle_files:
            missing_series.append(series_dir.name)

if missing_series:
    print("Séries sans sous-titres valides :")
    for s in missing_series:
        print(f" - {s}")
else:
    print("Toutes les séries ont au moins un fichier .srt ou .sub.")
