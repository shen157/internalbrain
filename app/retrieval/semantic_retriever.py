from sentence_transformers import SentenceTransformer
import numpy as np

from app.retrieval.text_utils import (
    build_search_text
)


_MODEL_CACHE = {}


def get_embedding_model(model_name):

    if model_name not in _MODEL_CACHE:

        _MODEL_CACHE[model_name] = (
            SentenceTransformer(
                model_name
            )
        )

    return _MODEL_CACHE[model_name]


class SemanticRetriever:

    def __init__(
        self,
        resources,
        model_name="sentence-transformers/all-MiniLM-L6-v2"
    ):

        self.resources = resources

        self.model = get_embedding_model(
            model_name
        )

        self.documents = [
            build_search_text(resource)
            for resource in resources
        ]

        if self.documents:

            self.embeddings = (
                self.model.encode(
                    self.documents,
                    normalize_embeddings=True
                )
            )

        else:
            self.embeddings = None


    def search(
        self,
        query,
        top_k=5,
        min_score=0.35
    ):

        if not self.resources:
            return []

        query_embedding = (
            self.model.encode(
                [query],
                normalize_embeddings=True
            )[0]
        )

        scores = np.dot(
           self.embeddings,
            query_embedding
        )

        ranked_indices = np.argsort(
            scores
        )[::-1]

        results = []

        for index in ranked_indices:

            score = float(
                scores[index]
            )

            if score < min_score:
                continue

            results.append({
                "resource":
                    self.resources[index],

                "score":
                    score
            })

            if len(results) >= top_k:
                break

        return results