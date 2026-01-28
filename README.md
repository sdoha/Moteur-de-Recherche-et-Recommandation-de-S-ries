# SUBSTREAM — moteur de recherche de séries basé sur les sous-titres

Projet Flask : recherche TF-IDF sur sous-titres, recommandations, notes et liste personnelle.

## Binôme et groupe
- **Noms** : Doha SLITH, Mouataz LFARH, Baptiste CHA  
- **Groupe** : D  
- **Statut** : Non-alternants

## Lancement rapide
1. (Optionnel) Créer/activer un venv, puis `pip install -r requirements.txt`.
2. Vérifier que `database/tvshow.db` est présent (via Git LFS si besoin).
3. Lancer : `python app.py` (ou `python3 app.py`).
4. Ouvrir : `http://127.0.0.1:5000`.

## Contenu principal
- `app.py` : routes Flask (API + HTML)
- `search.py` : moteur TF-IDF
- `recommend.py` : recommandations contenu/profil
- `templates/`, `static/` : pages et JS/CSS
- `scripts/` : ETL sous-titres / import termes
- `database/tvshow.db` : base SQLite (via LFS)
- `tests/` : tests pytest (optionnel)

## Données volumineuses non incluses (pour une archive légère)
- `sous-titres/` (~770 Mo)
- `data_word_frequency_clean/`
- `database/tvshow.db` complet (>100 Mo, via Git LFS)  
  Si besoin : `git lfs install && git lfs pull` pour récupérer la base.
