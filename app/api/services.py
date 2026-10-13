from app.retrieval.retrieval_service import (
    RetrievalService
)

from app.llm.answer_service import (
    AnswerService
)

from app.sync.sync_service import (
    SyncService
)

from app.security.audit_logger import (
    AuditLogger
)


# =========================================================
# Shared Services
# =========================================================

audit_logger = (
    AuditLogger()
)


retrieval_service = (
    RetrievalService()
)


answer_service = (
    AnswerService(
        retrieval_service=
            retrieval_service,

        audit_logger=
            audit_logger
    )
)


sync_service = (
    SyncService(
        retrieval_service=
            retrieval_service,

        permission_store=
            retrieval_service
            .permission_store,

        audit_logger=
            audit_logger
    )
)