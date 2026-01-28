"""app.py - Application Flask (vues HTML + APIs : auth, recherche, reco, listes, séries)."""
import os
import sqlite3
from typing import Dict, Optional, Tuple

import numpy as np
from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
 
from recommend import recommend_by_content, recommend_for_user, warm_recommendation_model
from search import SearchEngine

app = Flask(__name__)
app.secret_key = "ton_secret_key"

DB_PATH = os.path.join(app.root_path, "database", "tvshow.db")


# get_db_connection : ouvre une connexion SQLite (row_factory configurée)
def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


search_engine: Optional[SearchEngine] = None
series_meta_by_name: Dict[str, Tuple[int, Optional[str], Optional[str]]] = {}
series_meta_by_id: Dict[int, Tuple[str, Optional[str], Optional[str]]] = {}

# init_search : instancie le moteur TF-IDF en mémoire
def init_search(force: bool = False) -> None:
    global search_engine
    if search_engine is not None and not force:
        return
    series_counts = SearchEngine.load_series_counts_from_db()
    search_engine = SearchEngine(series_counts)



# load_series_meta : met en cache les métadonnées des séries
def load_series_meta(force: bool = False) -> Dict[str, Tuple[int, Optional[str], Optional[str]]]:
    global series_meta_by_name, series_meta_by_id
    if series_meta_by_name and not force:
        return series_meta_by_name

    conn = get_db_connection()
    try:
        rows = conn.execute("SELECT id, name, image_url, synopsis FROM tvshow").fetchall()
        series_meta_by_name = {}
        series_meta_by_id = {}
        for row in rows:
            info_name = (row["id"], row["image_url"], row["synopsis"])
            info_id = (row["name"], row["image_url"], row["synopsis"])
            series_meta_by_name[row["name"]] = info_name
            series_meta_by_id[row["id"]] = info_id
    finally:
        conn.close()
    return series_meta_by_name


# Pre-warm recommendation model to avoid first-request latency
warm_recommendation_model()


# -----------------------------
# --- VUES HTML (affichage) ---
# -----------------------------
@app.route("/login", methods=["GET"])
# Nom : login
# But : afficher la page de connexion (auth via /api/login en JS)
def login():
    # Affichage uniquement : l'auth se fait via l'API /api/login en front
    return render_template("login.html", errors=[])


@app.route("/signup", methods=["GET"])
# Nom : signup
# But : afficher la page d'inscription (inscription via /api/signup en JS)
def signup():
    # Affichage uniquement : l'inscription se fait via l'API /api/signup en front
    return render_template("signup.html")


@app.route("/forgot-password", methods=["GET", "POST"])
# Nom : forgot_password
# But : déclencher un reset simple via session (démo sans email)
def forgot_password():
    if request.method == "POST":
        email = request.form.get("email", "").strip()
        if not email:
            flash("Indique ton email.", "error")
            return redirect(url_for("forgot_password"))

        conn = get_db_connection()
        user = conn.execute(
            "SELECT username FROM user WHERE email = ?", (email,)
        ).fetchone()
        conn.close()

        if user:
            session["reset_user"] = user["username"]
            flash("Utilisateur identifié. Choisis ton nouveau mot de passe.", "success")
            return redirect(url_for("reset_password_simple"))

        flash("Si cet email existe, un lien de réinitialisation a été envoyé.", "success")
        return redirect(url_for("login"))

    return render_template("forgot_password.html")


@app.route("/reset-password-simple", methods=["GET", "POST"])
# Nom : reset_password_simple
# But : mettre à jour le mot de passe après identification en session
def reset_password_simple():
    if "reset_user" not in session:
        flash("Aucune demande de réinitialisation en cours.", "error")
        return redirect(url_for("login"))

    if request.method == "POST":
        new_password = request.form.get("password", "")
        confirm_password = request.form.get("confirm_password", "")

        if new_password != confirm_password:
            flash("Les mots de passe ne correspondent pas.", "error")
            return redirect(url_for("reset_password_simple"))

        hashed_password = generate_password_hash(new_password)
        conn = get_db_connection()
        conn.execute(
            "UPDATE user SET password_hash = ? WHERE username = ?",
            (hashed_password, session["reset_user"]),
        )
        conn.commit()
        conn.close()

        session.pop("reset_user", None)
        flash("Mot de passe réinitialisé avec succès.", "success")
        return redirect(url_for("login"))

    return render_template("reset_password.html")


@app.route("/logout")
# Nom : logout
# But : vider la session utilisateur et revenir à l'accueil
def logout():
    session.pop("user", None)
    flash("Deconnecte avec succes.")
    return redirect(url_for("index"))


@app.route("/")
# Nom : index
# But : afficher l'accueil (hero et JS consomme /api/series)
def index():
    hero_folder = os.path.join(app.static_folder, "images", "hero")
    hero_images = []
    if os.path.exists(hero_folder):
        hero_images = [
            filename
            for filename in os.listdir(hero_folder)
            if filename.lower().endswith((".png", ".jpg", ".jpeg", ".gif", ".webp"))
        ]

    hero_urls = [
        url_for("static", filename=f"images/hero/{filename}") for filename in hero_images
    ]

    # Le front consomme /api/series pour afficher les séries (visibilité).
    return render_template("index.html", series=[], hero_urls=hero_urls)


@app.route("/series/<int:series_id>")
# Nom : series_detail
# But : afficher la fiche HTML (notes, liste, similaires)
def series_detail(series_id: int):
    conn = get_db_connection()
    serie = conn.execute("SELECT * FROM tvshow WHERE id = ?", (series_id,)).fetchone()

    user_rating = None
    in_list = False
    avg_rating = None

    if serie:
        avg_row = conn.execute(
            "SELECT AVG(rating) AS avg_rating FROM ratings WHERE tvshow_name = ?",
            (serie["name"],),
        ).fetchone()
        if avg_row and avg_row["avg_rating"]:
            avg_rating = round(avg_row["avg_rating"], 1)

        if "user" in session:
            user_rating_row = conn.execute(
                "SELECT rating FROM ratings WHERE username = ? AND tvshow_name = ?",
                (session["user"], serie["name"]),
            ).fetchone()
            if user_rating_row:
                user_rating = user_rating_row["rating"]

            in_list_row = conn.execute(
                "SELECT 1 FROM mylist WHERE username = ? AND tvshow_id = ?",
                (session["user"], serie["id"]),
            ).fetchone()
            in_list = bool(in_list_row)

    conn.close()

    if not serie:
        flash("Serie introuvable.")
        return redirect(url_for("index"))

    return render_template(
        "series_detail.html",
        serie=serie,
        user_rating=user_rating,
        avg_rating=avg_rating,
        in_list=in_list,
    )


# -----------------------------
# --- API RECHERCHE (TF-IDF) ---
# -----------------------------
@app.route("/api/search")
# Nom : api_search
# But : chercher des séries par mots-clés (TF-IDF)
def api_search():
    query = request.args.get("q", "").strip()
    if not query:
        return jsonify({"query": query, "count": 0, "results": []})

    init_search()
    series_meta = load_series_meta()

    if search_engine is None or not series_meta:
        return jsonify({"query": query, "count": 0, "results": []})

    query_counts = SearchEngine._query_to_counts(query)
    query_tokens = list(query_counts.keys())
    if not query_tokens:
        return jsonify({"query": query, "count": 0, "results": []})

    keyword_scores = search_engine.keyword_scores(query_tokens)
    if not keyword_scores:
        return jsonify({"query": query, "count": 0, "results": []})

    token_indices = search_engine.get_token_indices(query_tokens)
    tfidf_scores: Dict[str, float] = {}
    if token_indices and len(token_indices) == len(query_tokens):
        q_vector = search_engine.vectorize_query(query)
        sims = (q_vector @ search_engine._X.T).toarray().ravel()
        coverage_mask = search_engine._X[:, token_indices].getnnz(axis=1) == len(token_indices)
        candidate_indices = np.where(coverage_mask)[0]

        series_names = search_engine.series_names
        for idx in candidate_indices:
            name = series_names[idx]
            if name in keyword_scores:
                tfidf_scores[name] = float(sims[idx])

    results = []
    for name, kw_score in keyword_scores.items():
        tf_score = tfidf_scores.get(name)
        if tf_score is None:
            continue

        combined_score = 0.7 * tf_score + 0.3 * kw_score
        if combined_score < 0.25:
            continue

        meta = series_meta.get(name)
        if not meta:
            continue
        serie_id, image_url, synopsis = meta
        results.append((combined_score, name, image_url, serie_id, synopsis))

    results.sort(key=lambda item: item[0], reverse=True)
    payload = [
        {
            "name": name,
            "image_url": image_url,
            "id": serie_id,
            "synopsis": synopsis or "",
            "score": round(min(score, 1.0), 3),
        }
        for score, name, image_url, serie_id, synopsis in results[:10]
    ]

    return jsonify({"query": query, "count": len(payload), "results": payload})

# -----------------------------
# --- API RECOMMANDATION ---
# -----------------------------
@app.route("/api/similar/<int:series_id>")
# Nom : api_similar
# But : retourner des séries similaires (contenu)
def api_similar(series_id: int):
    """
    Retourne les séries similaires à une série donnée.
    Basé sur la similarité TF-IDF des synopsis.
    """
    # Charger les métadonnées de la série actuelle
    conn = get_db_connection()
    serie = conn.execute(
        "SELECT id, name, image_url, synopsis FROM tvshow WHERE id = ?", (series_id,)
    ).fetchone()
    conn.close()

    if not serie:
        return jsonify({"results": []})

    current_name = serie["name"]

    # Appeler le moteur de recommandation par contenu
    try:
        similar_series = recommend_by_content(current_name, top_n=6)
    except Exception as e:
        print("Erreur reco contenu:", e)
        return jsonify({"results": []})

    # Charger les infos des séries similaires depuis la base
    similar_names = [name for name, _ in similar_series]
    if not similar_names:
        return jsonify({"results": []})

    conn = get_db_connection()
    placeholders = ",".join("?" for _ in similar_names)
    rows = conn.execute(
        f"SELECT id, name, image_url, synopsis FROM tvshow WHERE name IN ({placeholders})",
        similar_names,
    ).fetchall()
    conn.close()

    # Créer une table de correspondance nom → meta
    meta = {row["name"]: row for row in rows}

    # Construire la réponse dans le même ordre que les similarités
    results = []
    for name, score in similar_series:
        if name not in meta:
            continue
        s = meta[name]
        results.append({
            "id": s["id"],
            "name": s["name"],
            "image_url": s["image_url"],
            "synopsis": s["synopsis"] or "",
            "score": round(score, 3),
        })

        # éviter de retourner plus que 5 résultats
        if len(results) >= 5:
            break

    return jsonify({"base_series": current_name, "results": results})



# -----------------------------
# --- API NOTES / LISTE ---
# -----------------------------
@app.route("/api/rate", methods=["POST"])
# Nom : api_rate
# But : enregistrer une note (1-5) pour une série
def api_rate():
    if "user" not in session:
        return jsonify({"success": False, "error": "Vous devez etre connecte pour noter une serie."})

    data = request.get_json() or {}
    serie_name = data.get("serie_name")
    rating = data.get("rating")
    username = session["user"]

    if not serie_name or rating is None:
        return jsonify({"success": False, "error": "Donnees manquantes."})

    try:
        rating = int(rating)
        if rating < 1 or rating > 5:
            raise ValueError
    except ValueError:
        return jsonify({"success": False, "error": "Note invalide."})

    conn = get_db_connection()
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS ratings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL,
            tvshow_name TEXT NOT NULL,
            rating INTEGER NOT NULL,
            UNIQUE(username, tvshow_name)
        )
        """
    )
    conn.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS idx_ratings_user_show
        ON ratings(username, tvshow_name)
        """
    )
    conn.execute(
        """
        INSERT INTO ratings (username, tvshow_name, rating)
        VALUES (?, ?, ?)
        ON CONFLICT(username, tvshow_name)
        DO UPDATE SET rating = excluded.rating
        """,
        (username, serie_name, rating),
    )
    conn.commit()
    conn.close()

    return jsonify({"success": True})


@app.route("/api/toggle_list", methods=["POST"])
# Nom : api_toggle_list
# But : ajouter/retirer une série de la liste perso
def api_toggle_list():
    if "user" not in session:
        return jsonify({"success": False, "error": "Vous devez etre connecte pour gerer votre liste."})

    data = request.get_json() or {}
    serie_id = data.get("serie_id")
    username = session["user"]

    if not serie_id:
        return jsonify({"success": False, "error": "ID serie manquant."})

    conn = get_db_connection()
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS mylist (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL,
            tvshow_id INTEGER NOT NULL,
            UNIQUE(username, tvshow_id) ON CONFLICT REPLACE
        )
        """
    )

    row = conn.execute(
        "SELECT 1 FROM mylist WHERE username = ? AND tvshow_id = ?",
        (username, serie_id),
    ).fetchone()

    if row:
        conn.execute(
            "DELETE FROM mylist WHERE username = ? AND tvshow_id = ?",
            (username, serie_id),
        )
        action = "removed"
    else:
        conn.execute(
            "INSERT INTO mylist (username, tvshow_id) VALUES (?, ?)",
            (username, serie_id),
        )
        action = "added"

    conn.commit()
    conn.close()
    return jsonify({"success": True, "action": action})


@app.route("/api/recommend/<serie_name>")
# Nom : api_recommend_content
# But : recommandations par contenu à partir du nom
def api_recommend_content(serie_name: str):
    recos = recommend_by_content(serie_name, top_n=5)
    conn = get_db_connection()
    enriched = []
    try:
        for name, score in recos:
            row = conn.execute(
                "SELECT id, name, image_url FROM tvshow WHERE lower(name) = ? LIMIT 1",
                (str(name).lower(),),
            ).fetchone()
            if row:
                enriched.append(
                    {
                        "id": row["id"],
                        "name": row["name"],
                        "image_url": row["image_url"],
                        "score": float(score),
                    }
                )
    finally:
        conn.close()
    return jsonify({"serie": serie_name, "recommendations": enriched})


@app.route("/api/recommend_user")
# Nom : api_recommend_user
# But : recommandations personnalisées selon les notes
def api_recommend_user():
    if "user" not in session:
        return jsonify({"error": "Connectez-vous pour voir vos recommandations."})

    recos = recommend_for_user(session["user"], top_n=10)
    conn = get_db_connection()
    enriched = []
    try:
        for name, score in recos:
            row = conn.execute(
                "SELECT id, name, image_url, synopsis FROM tvshow WHERE lower(name) = ? LIMIT 1",
                (str(name).lower(),),
            ).fetchone()
            if row:
                enriched.append(
                    {
                        "id": row["id"],
                        "name": row["name"],
                        "image_url": row["image_url"],
                        "synopsis": row["synopsis"] or "",
                        "score": float(score),
                    }
                )
    finally:
        conn.close()
    return jsonify({"user": session["user"], "recommendations": enriched})

# ----------------------------
# API visibilité des séries
# ----------------------------
@app.route("/api/series")
# Nom : api_series_list
# But : liste JSON des séries (visibilité)
def api_series_list():
    """Retourne la liste des séries (id, name, image_url, synopsis)."""
    conn = get_db_connection()
    rows = conn.execute(
        """
        SELECT id, name, image_url, synopsis
        FROM tvshow
        WHERE name IS NOT NULL AND name != ''
        ORDER BY id ASC
        """
    ).fetchall()
    conn.close()
    payload = [
        {
            "id": row["id"],
            "name": row["name"],
            "image_url": row["image_url"],
            "synopsis": row["synopsis"] or "",
        }
        for row in rows
    ]
    return jsonify({"count": len(payload), "results": payload})


@app.route("/api/series/<int:series_id>")
# Nom : api_series_detail
# But : détail JSON d'une série
def api_series_detail(series_id: int):
    """Retourne le détail d'une série."""
    conn = get_db_connection()
    row = conn.execute(
        "SELECT id, name, image_url, synopsis FROM tvshow WHERE id = ?",
        (series_id,),
    ).fetchone()
    conn.close()
    if not row:
        return jsonify({"error": "Serie introuvable."}), 404
    return jsonify(
        {
            "id": row["id"],
            "name": row["name"],
            "image_url": row["image_url"],
            "synopsis": row["synopsis"] or "",
        }
    )


# ----------------------------
# API gestion des comptes (JSON)
# ----------------------------
@app.route("/api/signup", methods=["POST"])
# Nom : api_signup
# But : créer un utilisateur et le connecter en session (JSON)
def api_signup():
    data = request.get_json() or {}
    username = (data.get("username") or "").strip()
    email = (data.get("email") or "").strip()
    password = data.get("password") or ""
    confirm_password = data.get("confirm_password") or password

    if not username or not email or not password:
        return jsonify({"success": False, "error": "Champs manquants."}), 400
    if password != confirm_password:
        return jsonify({"success": False, "error": "Les mots de passe ne correspondent pas."}), 400

    hashed_password = generate_password_hash(password)
    conn = get_db_connection()
    try:
        conn.execute(
            "INSERT INTO user (username, email, password_hash) VALUES (?, ?, ?)",
            (username, email, hashed_password),
        )
        conn.commit()
    except sqlite3.IntegrityError:
        return jsonify({"success": False, "error": "Nom d'utilisateur ou email déjà utilisé."}), 400
    finally:
        conn.close()

    session["user"] = username
    return jsonify({"success": True, "user": username})


@app.route("/api/login", methods=["POST"])
# Nom : api_login
# But : connecter un utilisateur en session (JSON)
def api_login():
    data = request.get_json() or {}
    username = (data.get("username") or "").strip()
    password = data.get("password") or ""

    if not username or not password:
        return jsonify({"success": False, "error": "Champs manquants."}), 400


    conn = get_db_connection()
    user = conn.execute("SELECT * FROM user WHERE username = ?", (username,)).fetchone()
    conn.close()

    if user and check_password_hash(user["password_hash"], password):
        session["user"] = user["username"]
        return jsonify({"success": True, "user": user["username"]})

    return jsonify({"success": False, "error": "Nom d'utilisateur ou mot de passe incorrect."}), 401


@app.route("/api/logout", methods=["POST"])
# Nom : api_logout
# But : déconnecter l'utilisateur courant (JSON)
def api_logout():
    session.pop("user", None)
    return jsonify({"success": True})


@app.route("/maliste")
def maliste():
    if "user" not in session:
        flash("Vous devez etre connecte pour acceder a votre liste.")
        return redirect(url_for("login"))

    conn = get_db_connection()
    mylist = conn.execute(
        """
        SELECT tvshow.id, tvshow.name, tvshow.image_url
        FROM mylist
        JOIN tvshow ON mylist.tvshow_id = tvshow.id
        WHERE mylist.username = ?
        """,
        (session["user"],),
    ).fetchall()
    conn.close()

    return render_template("maliste.html", mylist=mylist)


@app.route("/mesnotations")
# Nom : mesnotations
# But : afficher les séries notées par l'utilisateur (page HTML)
def mesnotations():
    if "user" not in session:
        flash("Vous devez etre connecte pour voir vos notations.")
        return redirect(url_for("login"))
    return render_template("mesnotations.html")


@app.route("/api/my_ratings")
# Nom : api_my_ratings
# But : retourner les séries notées par l'utilisateur avec sa note et la moyenne globale
def api_my_ratings():
    if "user" not in session:
        return jsonify({"error": "Unauthorized"}), 401

    username = session["user"]
    conn = get_db_connection()
    rows = conn.execute(
        """
        SELECT
          tvshow.id AS id,
          tvshow.name AS name,
          tvshow.image_url AS image_url,
          r.rating AS user_rating,
          (
            SELECT ROUND(AVG(r2.rating), 1)
            FROM ratings r2
            WHERE lower(r2.tvshow_name) = lower(tvshow.name)
          ) AS avg_rating
        FROM ratings r
        JOIN tvshow ON lower(tvshow.name) = lower(r.tvshow_name)
        WHERE r.username = ?
        ORDER BY tvshow.name ASC
        """,
        (username,),
    ).fetchall()
    conn.close()

    results = [
        {
            "id": row["id"],
            "name": row["name"],
            "image_url": row["image_url"],
            "user_rating": row["user_rating"],
            "avg_rating": row["avg_rating"] or 0,
        }
        for row in rows
    ]
    return jsonify({"count": len(results), "results": results})


if __name__ == "__main__":
    init_search()
    load_series_meta()
    warm_recommendation_model()
    app.run(debug=True)

