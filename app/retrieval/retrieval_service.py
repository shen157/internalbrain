from app.data.loader import (
    get_user
)

from app.connectors.registry import (
    load_all_resources
)

from app.auth.permission_store import (
    PermissionStore
)

from app.auth.permission_engine import (
    PermissionEngine
)

from app.retrieval.bm25_retriever import (
    BM25Retriever
)

from app.retrieval.semantic_retriever import (
    SemanticRetriever
)

from app.retrieval.hybrid_retriever import (
    HybridRetriever
)

class RetrievalService:

    def __init__(
        self,
        resources=None,
        permission_store=None
    ):

        self.resources = (
            resources
            if resources is not None
            else load_all_resources()
        )

        self.permission_store = (
            permission_store
            if permission_store is not None
            else PermissionStore()
        )

        self.permission_engine = (
            PermissionEngine(
                self.permission_store
            )
        )

    def replace_resources(
        self,
        resources
    ):

        self.resources = list(
            resources
        )

    def resource_count(self):

        return len(
            self.resources
        )

    def get_authorized_resources(
        self,
        user
    ):

        authorized = []

        for resource in self.resources:

            if (
                self.permission_engine
                .can_access(
                    user,
                    resource
                )
            ):
                authorized.append(
                    resource
                )

        return authorized


    def search(
        self,
        user_id,
        query,
        top_k=5,
        method="bm25"
    ):

        user = get_user(
            user_id
        )

        authorized_resources = (
            self.get_authorized_resources(
                user
            )
        )


        if method == "bm25":

            retriever = BM25Retriever(
                authorized_resources
            )


        elif method == "semantic":

            retriever = SemanticRetriever(
                authorized_resources
            )

        elif method == "hybrid":

            retriever = HybridRetriever(
                authorized_resources
            )

        else:

            raise ValueError(
                f"Unknown retrieval method: "
                f"{method}"
            )


        results = retriever.search(
            query=query,
            top_k=top_k
        )


        return {
            "user_id":
                user_id,

            "query":
                query,

            "method":
                method,

            "total_resources":
                len(self.resources),

            "authorized_resources":
                len(
                    authorized_resources
                ),

            "results":
                results
        }