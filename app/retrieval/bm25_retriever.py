from rank_bm25 import BM25Okapi

from app.retrieval.text_utils import (
    tokenize,
    build_search_text
)


class BM25Retriever:

    def __init__(self, resources):

        self.resources = resources

        self.corpus_tokens = [
            tokenize(
                build_search_text(resource)
            )
            for resource in resources
        ]

        self.bm25 = (
            BM25Okapi(
                self.corpus_tokens
            )
            if self.corpus_tokens
            else None
        )


    def search(
        self,
        query,
        top_k=5
    ):

        if not self.resources:
            return []

        query_tokens = tokenize(query)

        if not query_tokens:
            return []

        scores = self.bm25.get_scores(
            query_tokens
        )

        ranked = sorted(
            zip(
                self.resources,
                scores
            ),
            key=lambda x: x[1],
            reverse=True
        )

        results = []

        for resource, score in ranked:

            if score <= 0:
                continue

            results.append({
                "resource": resource,
                "score": float(score)
            })

            if len(results) >= top_k:
                break

        return results