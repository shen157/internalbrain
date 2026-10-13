# InternalBrain frontend package.
#
# The frontend talks to the existing FastAPI backend over HTTP only.
# It must never import backend modules (AnswerService, RetrievalService,
# PermissionStore, Tencent TokenHub, etc.) directly.
