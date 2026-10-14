"""RAG retrieval module using ChromaDB and SentenceTransformers with TF-IDF fallback."""
from pathlib import Path
import shutil
import logging
from typing import List, Tuple

from stripewatch.config import (
    CHROMA_DIR,
    EMBEDDING_MODEL_NAME,
    NOTES_FILE,
    NOTES_STRUCTURED_FILE
)
from stripewatch.notes import Note, load_structured_notes

logger = logging.getLogger(__name__)

COLLECTION_NAME = "stripewatch_notes"


class NoteRetriever:
    """Retriever for freight context notes."""

    def __init__(self, notes: List[Note] | None = None, persist_dir: Path = CHROMA_DIR, use_tfidf: bool = False):
        self.persist_dir = Path(persist_dir)
        self.use_tfidf = use_tfidf
        self.notes = notes if notes is not None else load_structured_notes()
        self.notes_by_id = {n.id: n for n in self.notes}
        self._init_backend()

    def _init_backend(self):
        if self.use_tfidf:
            self._init_tfidf()
            return

        try:
            import chromadb
            from sentence_transformers import SentenceTransformer

            # Fresh collection for determinism
            if self.persist_dir.exists():
                shutil.rmtree(self.persist_dir, ignore_errors=True)
            self.persist_dir.mkdir(parents=True, exist_ok=True)

            self.client = chromadb.PersistentClient(path=str(self.persist_dir))
            self.embedding_model = SentenceTransformer(EMBEDDING_MODEL_NAME)
            self.collection = self.client.create_collection(
                name=COLLECTION_NAME,
                metadata={"hnsw:space": "cosine"}
            )

            # Populate with all 10 notes
            ids = [n.id for n in self.notes]
            # Embed full raw note text + applies_to for rich matching
            documents = [f"Route: {n.applies_to}. Date: {n.date}. Note: {n.text}" for n in self.notes]
            metadatas = [{"id": n.id, "applies_to": n.applies_to, "date": n.date} for n in self.notes]
            embeddings = self.embedding_model.encode(documents, normalize_embeddings=True).tolist()

            self.collection.add(
                ids=ids,
                documents=documents,
                metadatas=metadatas,
                embeddings=embeddings
            )
            self.backend = "chroma"
        except Exception as e:
            logger.warning(f"Failed to initialize Chroma/SentenceTransformers: {e}. Falling back to TF-IDF.")
            self._init_tfidf()

    def _init_tfidf(self):
        from sklearn.feature_extraction.text import TfidfVectorizer
        from sklearn.metrics.pairwise import cosine_similarity

        self.backend = "tfidf"
        self.vectorizer = TfidfVectorizer()
        docs = [f"Route: {n.applies_to}. Date: {n.date}. Note: {n.text}" for n in self.notes]
        self.tfidf_matrix = self.vectorizer.fit_transform(docs)
        self.cosine_similarity = cosine_similarity

    def retrieve(self, query: str, k: int = 3) -> List[Tuple[str, float]]:
        """Retrieve top-k notes for a query string.

        Returns:
            List of (note_id, similarity_score) tuples, sorted by score descending,
            with ties broken by note_id ascending.
        """
        k = min(k, len(self.notes))
        if self.backend == "chroma":
            query_emb = self.embedding_model.encode([query], normalize_embeddings=True).tolist()
            res = self.collection.query(
                query_embeddings=query_emb,
                n_results=k
            )
            ids = res["ids"][0]
            distances = res["distances"][0]
            # Chroma cosine distance = 1 - cosine_similarity
            hits = []
            for nid, dist in zip(ids, distances):
                sim = max(0.0, 1.0 - dist)
                hits.append((nid, round(sim, 4)))
        else:
            query_vec = self.vectorizer.transform([query])
            sims = self.cosine_similarity(query_vec, self.tfidf_matrix)[0]
            scored = [(self.notes[i].id, round(float(sims[i]), 4)) for i in range(len(self.notes))]
            hits = sorted(scored, key=lambda x: (-x[1], x[0]))[:k]

        # Break ties deterministically by (-score, note_id)
        hits.sort(key=lambda x: (-x[1], x[0]))
        return hits

    def retrieve_for_candidate(self, route: str, week_of_str: str, k: int = 3) -> List[Tuple[str, float]]:
        """Retrieve top notes for a specific route and week using route-specific and nationwide queries."""
        try:
            import pandas as pd
            dt = pd.to_datetime(week_of_str)
            month_name = dt.strftime("%B")
            year_str = dt.strftime("%Y")
        except Exception:
            month_name = ""
            year_str = ""

        q1 = f"{route} freight cost increase week of {week_of_str} reason"
        q2 = f"nationwide freight cost increase {month_name} {year_str} diesel fuel toll"

        hits1 = self.retrieve(q1, k=k)
        hits2 = self.retrieve(q2, k=k)

        # Merge deduplicating by best score
        score_map = {}
        for nid, score in hits1 + hits2:
            if nid not in score_map or score > score_map[nid]:
                score_map[nid] = score

        merged = sorted(score_map.items(), key=lambda x: (-x[1], x[0]))[:k]
        return merged
