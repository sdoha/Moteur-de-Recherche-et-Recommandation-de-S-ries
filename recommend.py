"""Content-based recommendation helpers for SUBSTREAM."""

from __future__ import annotations

import os
import re
import sqlite3
import unicodedata
from collections import Counter, defaultdict
from typing import Dict, Iterable, List, Sequence, Tuple

import numpy as np
from scipy.sparse import csr_matrix
from sklearn.feature_extraction import DictVectorizer
from sklearn.feature_extraction.text import TfidfTransformer
from sklearn.metrics.pairwise import cosine_similarity
from sklearn.preprocessing import normalize

DB_PATH = os.path.join(os.path.dirname(__file__), "database", "tvshow.db")

# Very small bilingual stop-word list to keep only meaningful terms.
STOP_WORDS = {
    "a",
    "and",
    "are",
    "au",
    "aux",
    "avec",
    "ce",
    "ces",
    "cet",
    "cette",
    "de",
    "des",
    "du",
    "elle",
    "elles",
    "en",
    "est",
    "et",
    "ils",
    "is",
    "la",
    "le",
    "les",
    "mais",
    "not",
    "of",
    "on",
    "ou",
    "par",
    "pour",
    "sans",
    "se",
    "son",
    "sur",
    "the",
    "their",
    "they",
    "to",
    "un",
    "une",
    "vous",
}

# Cached recommendation artefacts (lazy loaded).
_series_names: List[str] = []
_name_to_index: Dict[str, int] = {}
_content_matrix: csr_matrix | None = None

TOKEN_RE = re.compile(r"[\w']+", re.UNICODE)


# ---------------------------------------------------------------------------
# Database helper
# ---------------------------------------------------------------------------
# Nom : get_db_connection
# But : ouvrir une connexion SQLite avec row_factory
def get_db_connection() -> sqlite3.Connection:
    """Ouvre une connexion SQLite avec row_factory."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


# ---------------------------------------------------------------------------
# Text helpers
# ---------------------------------------------------------------------------
def _normalise_token(token: str) -> str:
    token = unicodedata.normalize("NFKC", token or "").lower()
    token = token.strip("_'")
    if len(token) <= 2 or token in STOP_WORDS:
        return ""
    return token


def _tokenise(text: str) -> List[str]:
    tokens = []
    for raw in TOKEN_RE.findall(text.lower()):
        token = _normalise_token(raw)
        if token:
            tokens.append(token)
    return tokens


# ---------------------------------------------------------------------------
# Feature construction
# ---------------------------------------------------------------------------
# Nom : _build_feature_space
# But : assembler les features (termes, synopsis, bigrammes) pondérées pour chaque série
def _build_feature_space(
    max_repeat: int = 8,
    term_weight: float = 2.0,
    synopsis_weight: float = 0.6,
    bigram_weight: float = 0.3,
) -> Tuple[List[str], List[Dict[str, float]]]:
    """
    Build feature dictionaries for every show by combining indexed terms and synopsis.
    Terms (from subtitles) are given a stronger weight than synopsis tokens.
    """
    conn = get_db_connection()
    cur = conn.cursor()

    shows = cur.execute(
        """
        SELECT id, name, COALESCE(synopsis, '') AS synopsis
        FROM tvshow
        ORDER BY id
        """
    ).fetchall()

    term_rows = cur.execute(
        """
        SELECT tvshow_id, term, count
        FROM tvshow_term
        WHERE count > 0
        ORDER BY tvshow_id
        """
    ).fetchall()
    conn.close()

    terms_by_show: Dict[int, List[Tuple[str, float]]] = defaultdict(list)
    for row in term_rows:
        terms_by_show[row["tvshow_id"]].append((row["term"], row["count"]))

    names: List[str] = []
    feature_dicts: List[Dict[str, float]] = []

    for show in shows:
        name = (show["name"] or "").strip()
        if not name:
            continue

        synopsis_tokens = _tokenise(show["synopsis"] or "")
        term_features: Dict[str, float] = {}

        for term, count in terms_by_show.get(show["id"], []):
            token = _normalise_token(term)
            if not token:
                continue
            try:
                freq = float(count)
            except (TypeError, ValueError):
                continue
            if freq <= 0:
                continue
            weight = term_weight * min(max_repeat, max(1.0, round(freq)))
            key = f"term::{token}"
            term_features[key] = term_features.get(key, 0.0) + weight

        if synopsis_tokens:
            counts = Counter(synopsis_tokens)
            for token, freq in counts.items():
                key = f"syn::{token}"
                term_features[key] = term_features.get(key, 0.0) + synopsis_weight * freq

            if bigram_weight > 0 and len(synopsis_tokens) >= 2:
                for left, right in zip(synopsis_tokens, synopsis_tokens[1:]):
                    key = f"big::{left}_{right}"
                    term_features[key] = term_features.get(key, 0.0) + bigram_weight

        if term_features:
            names.append(name)
            feature_dicts.append(term_features)

    return names, feature_dicts


def _ensure_content_model(force: bool = False) -> None:
    """Construit/charge la matrice TF-IDF contenu si nécessaire (cache global)."""
    global _series_names, _name_to_index, _content_matrix

    if _content_matrix is not None and not force:
        return

    names, feature_dicts = _build_feature_space()
    if not names:
        _series_names = []
        _name_to_index = {}
        _content_matrix = None
        return

    vectorizer = DictVectorizer()
    counts_matrix = vectorizer.fit_transform(feature_dicts)
    transformer = TfidfTransformer(norm="l2", sublinear_tf=True, smooth_idf=True)
    tfidf_matrix = transformer.fit_transform(counts_matrix)
    _content_matrix = normalize(tfidf_matrix, norm="l2", copy=False)

    _series_names = names
    _name_to_index = {name.lower(): idx for idx, name in enumerate(names)}


def warm_recommendation_model(force: bool = False) -> None:
    """
    Public helper used at app startup to ensure the TF-IDF matrix
    is computed before the first request (avoids long latency).
    """
    _ensure_content_model(force=force)


# ---------------------------------------------------------------------------
# Utilities
# ---------------------------------------------------------------------------
def _top_indices(scores: np.ndarray, top_n: int) -> Iterable[int]:
    if top_n <= 0 or scores.ndim != 1 or scores.size == 0:
        return []
    slice_size = min(scores.size, max(2 * top_n, 10))
    top_slice = np.argpartition(scores, -slice_size)[-slice_size:]
    ordered = top_slice[np.argsort(scores[top_slice])[::-1]]
    return ordered


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------
# Nom : recommend_by_content
# But : retourner les séries les plus proches (sim contenu) pour une série donnée
def recommend_by_content(serie_name: str, top_n: int = 5) -> List[Tuple[str, float]]:
    """
    Return the closest series based on subtitles and synopsis similarity.
    """
    _ensure_content_model()
    if _content_matrix is None:
        return []

    idx = _name_to_index.get((serie_name or "").lower())
    if idx is None:
        return []

    row = _content_matrix[idx]
    scores = (row @ _content_matrix.T).toarray().ravel()
    scores[idx] = 0.0

    results: List[Tuple[str, float]] = []
    for pos in _top_indices(scores, top_n):
        score = float(scores[pos])
        if score <= 0:
            continue
        results.append((_series_names[pos], score))
        if len(results) >= top_n:
            break
    return results


# Nom : recommend_for_user
# But : recommandations personnalisées en combinant les notes de l'utilisateur et la matrice contenu
def recommend_for_user(username: str, top_n: int = 5) -> List[Tuple[str, float]]:
    """
    Blend user ratings with the content matrix to surface unseen similar shows.
    """
    _ensure_content_model()
    if _content_matrix is None:
        return []

    conn = get_db_connection()
    rows = conn.execute(
        "SELECT tvshow_name, rating FROM ratings WHERE username = ?",
        (username,),
    ).fetchall()
    conn.close()

    if not rows:
        return []

    rated_indices: List[Tuple[int, float]] = []
    for row in rows:
        idx = _name_to_index.get((row["tvshow_name"] or "").lower())
        if idx is not None:
            rated_indices.append((idx, float(row["rating"])))

    if not rated_indices:
        return []

    profile: csr_matrix | None = None
    weight_sum = 0.0
    for idx, weight in rated_indices:
        weight = max(weight, 0.0)
        if weight == 0:
            continue
        weight_sum += weight
        contribution = weight * _content_matrix[idx]
        profile = contribution if profile is None else profile + contribution

    if profile is None or weight_sum == 0.0:
        return []

    profile = profile / weight_sum
    profile = normalize(profile, norm="l2", copy=False)

    scores = cosine_similarity(profile, _content_matrix).ravel()
    for idx, _ in rated_indices:
        scores[idx] = 0.0

    results: List[Tuple[str, float]] = []
    for pos in _top_indices(scores, top_n):
        score = float(scores[pos])
        if score <= 0:
            continue
        results.append((_series_names[pos], score))
        if len(results) >= top_n:
            break
    return results


if __name__ == "__main__":
    _ensure_content_model(force=True)
    print(">>> Test reco par contenu pour 'Lost':")
    print(recommend_by_content("Lost", top_n=5))
    print("\n>>> Test reco pour utilisateur 'alice':")
    print(recommend_for_user("alice", top_n=5))
