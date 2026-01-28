"""
search.py
Role : moteur de recherche TF-IDF (normalisation, vectorisation, similarites).
"""

from __future__ import annotations

import os
import re
import sqlite3
import unicodedata
from typing import Dict, List, Optional, Tuple

import numpy as np  # noqa: F401 (kept for potential future extensions)
from scipy.sparse import csr_matrix
from sklearn.feature_extraction import DictVectorizer
from sklearn.feature_extraction.text import TfidfTransformer
from sklearn.preprocessing import normalize

DB_PATH = os.path.join(os.path.dirname(__file__), "database", "tvshow.db")


def get_db_connection():
    """Ouvre une connexion SQLite avec row_factory active."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


class SearchEngine:
    """
    Moteur de recherche base sur TF-IDF pour SUBSTREAM.
    - Analyse des sous-titres
    - Calcul de similarite cosinus
    """

    def __init__(self, series_counts: Dict[str, Dict[str, float]]):
        self._series_counts: Dict[str, Dict[str, float]] = series_counts
        self.series_names: List[str] = list(series_counts.keys())
        self._name_to_index: Dict[str, int] = {name: i for i, name in enumerate(self.series_names)}

        self._dv = DictVectorizer()
        counts_list = [series_counts[name] for name in self.series_names]

        if not counts_list:
            self._dv.fit([{}])
            self._tfidf = TfidfTransformer(norm="l2", use_idf=True, smooth_idf=True)
            self._X = csr_matrix((0, 0))
            return

        X_counts = self._dv.fit_transform(counts_list)
        self._tfidf = TfidfTransformer(norm="l2", use_idf=True, smooth_idf=True)
        self._X = self._tfidf.fit_transform(X_counts)
        self._X = normalize(self._X, norm="l2", copy=False)

    # ----------------------
    # Helpers
    # ----------------------
    @staticmethod
    def _normalize_text(text: str) -> str:
        if not text:
            return ""
        normalized = unicodedata.normalize("NFD", text)
        stripped = "".join(ch for ch in normalized if unicodedata.category(ch) != "Mn")
        return stripped.lower()

    @staticmethod
    def load_series_counts_from_db() -> Dict[str, Dict[str, float]]:
        """Charge les occurrences de mots depuis la table tvshow_term."""
        series_counts: Dict[str, Dict[str, float]] = {}
        conn = get_db_connection()
        try:
            cursor = conn.execute(
                """
                SELECT tvshow.name, tvshow_term.term, tvshow_term.count
                FROM tvshow_term
                JOIN tvshow ON tvshow_term.tvshow_id = tvshow.id
                WHERE tvshow_term.count > 0
                """
            )
            for raw_name, term, count in cursor:
                term_norm = SearchEngine._normalize_text(term or "")
                if not term_norm or count <= 0:
                    continue
                bag = series_counts.setdefault(str(raw_name), {})
                bag[term_norm] = bag.get(term_norm, 0.0) + float(count)
        except Exception as exc:  # pragma: no cover - simple trace
            print("Erreur chargement DB:", exc)
        finally:
            conn.close()
        return series_counts

    @staticmethod
    def _query_to_counts(query: str) -> Dict[str, float]:
        token_re = re.compile(r"[^\W\d_]+(?:'[^\W\d_]+)*")
        tokens = [SearchEngine._normalize_text(token) for token in token_re.findall(query)]
        counts: Dict[str, float] = {}
        for token in tokens:
            counts[token] = counts.get(token, 0.0) + 1.0
        return counts

    def vectorize_query(self, query: str) -> csr_matrix:
        if self._X.shape[1] == 0:
            return csr_matrix((1, 0))

        counts = self._query_to_counts(query)
        if not counts:
            return csr_matrix((1, self._X.shape[1]))

        vec = self._dv.transform([counts])
        vec_tfidf = self._tfidf.transform(vec)
        return normalize(vec_tfidf, norm="l2")

    # ----------------------
    # Recherche TF-IDF
    # ----------------------
    def search(self, query: Optional[str] = None, top_n: int = 50) -> List[Tuple[str, float]]:
        """Retourne les series classees par similarite TF-IDF."""
        if self._X.shape[0] == 0 or self._X.shape[1] == 0:
            return []
        if not query:
            return []

        qv = self.vectorize_query(query)
        sims = (qv @ self._X.T).toarray().ravel()

        q_counts = self._query_to_counts(query)
        q_tokens = set(q_counts.keys())
        token_indices = [self._dv.vocabulary_.get(token) for token in q_tokens if token in self._dv.vocabulary_]

        scored: List[Tuple[str, float]] = []
        for index, name in enumerate(self.series_names):
            score = float(sims[index])
            if score <= 0:
                continue

            # Bonus si tous les mots de la requete sont presents
            if token_indices:
                try:
                    row = self._X.getrow(index)
                    has_all = all(row[0, idx] > 0 for idx in token_indices)
                except Exception:
                    has_all = False
                if has_all:
                    score = min(1.0, score + 0.05)

            if score >= 0.05:
                scored.append((name, score))

        scored.sort(key=lambda item: item[1], reverse=True)
        return scored[:top_n]

    # ----------------------
    # Utilitaires d'accès interne
    # ----------------------
    def has_all_terms(self, series_name: str, token_indices: List[int]) -> bool:
        """True si la serie contient tous les tokens donnés."""
        if not token_indices:
            return True
        series_idx = self._name_to_index.get(series_name)
        if series_idx is None:
            return False
        row = self._X.getrow(series_idx)
        return all(row[0, idx] > 0 for idx in token_indices)

    def get_token_indices(self, tokens: List[str]) -> List[int]:
        indices: List[int] = []
        for token in tokens:
            idx = self._dv.vocabulary_.get(token)
            if idx is None:
                return []
            indices.append(idx)
        return indices

    def keyword_scores(self, tokens: List[str]) -> Dict[str, float]:
        """Score basé sur la présence stricte des tokens."""
        if not tokens:
            return {}

        scores: Dict[str, float] = {}
        for name in self.series_names:
            term_counts = self._series_counts.get(name, {})
            if all(token in term_counts for token in tokens):
                scores[name] = float(sum(term_counts[token] for token in tokens))
        return scores

    def similar_by_name(self, series_name: str, top_n: int = 5) -> List[Tuple[str, float]]:
        """Retourne les séries les plus proches en cosinus TF-IDF."""
        if self._X.shape[0] == 0 or self._X.shape[1] == 0:
            return []

        idx = self._name_to_index.get(series_name)
        if idx is None:
            return []

        sims = (self._X[idx] @ self._X.T).toarray().ravel()
        sims[idx] = 0.0

        if top_n <= 0:
            return []

        top_indices = np.argpartition(sims, -top_n)[-top_n:]
        top_indices = top_indices[np.argsort(sims[top_indices])[::-1]]

        results: List[Tuple[str, float]] = []
        for i in top_indices:
            score = float(sims[i])
            if score <= 0:
                continue
            results.append((self.series_names[i], score))
            if len(results) >= top_n:
                break
        return results


# ----------------------
# Recherche complémentaire par mots-clés
# ----------------------
def keyword_search(query: str, top_n: int = 50) -> List[Tuple[str, float]]:
    """
    Recherche SQL stricte : conserve uniquement les séries contenant tous les mots
    (termes de plus de 2 caractères) présents dans la requête.
    """
    from collections import defaultdict

    query_terms = [token.lower() for token in (query or "").split() if len(token) > 2]
    if not query_terms:
        return []

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    scores = defaultdict(float)
    found_terms = defaultdict(set)
    try:
        for term in query_terms:
            cursor = conn.execute(
                """
                SELECT tvshow.name, tvshow_term.count
                FROM tvshow_term
                JOIN tvshow ON tvshow_term.tvshow_id = tvshow.id
                WHERE lower(tvshow_term.term) = ?
                """,
                (term,),
            )
            for row in cursor:
                name = row["name"]
                scores[name] += float(row["count"] or 0.0)
                found_terms[name].add(term)
    finally:
        conn.close()

    must_have = set(query_terms)
    filtered: List[Tuple[str, float]] = [
        (name, scores[name])
        for name, terms in found_terms.items()
        if must_have.issubset(terms)
    ]
    filtered.sort(key=lambda item: item[1], reverse=True)
    return filtered[:top_n]
