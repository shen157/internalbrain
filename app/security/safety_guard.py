import re


# =========================================================
# Safety Messages
# =========================================================

BLOCKED_QUERY_MESSAGE = (
    "I cannot assist with attempts to bypass access controls "
    "or reveal restricted system information."
)


UNVERIFIED_ANSWER_MESSAGE = (
    "I could not produce a sufficiently verified answer "
    "from the authorized information."
)


# =========================================================
# Suspicious User Query Patterns
# =========================================================

QUERY_INJECTION_PATTERNS = [

    # -----------------------------------------------------
    # Instruction override
    # -----------------------------------------------------

    re.compile(
        r"\b("
        r"ignore|disregard|override|forget|replace|discard"
        r")\b"
        r".{0,100}"
        r"\b("
        r"previous|prior|system|developer|security|"
        r"instructions?|rules?|polic(?:y|ies)"
        r")\b",
        re.IGNORECASE
    ),


    # -----------------------------------------------------
    # Hidden prompt / internal instruction extraction
    # -----------------------------------------------------

    re.compile(
        r"\b("
        r"reveal|show|print|dump|display|expose|repeat|quote"
        r")\b"
        r".{0,100}"
        r"\b("
        r"system prompt|developer message|"
        r"hidden instructions?|internal instructions?|"
        r"secret prompt"
        r")\b",
        re.IGNORECASE
    ),


    # -----------------------------------------------------
    # Permission / RBAC bypass
    # -----------------------------------------------------

    re.compile(
        r"\b("
        r"bypass|circumvent|disable|skip|evade|"
        r"override|ignore"
        r")\b"
        r".{0,100}"
        r"\b("
        r"permission|permissions|rbac|access control|"
        r"authorization|authorisation|security checks?"
        r")\b",
        re.IGNORECASE
    ),


    # -----------------------------------------------------
    # Restricted resource probing:
    # action -> lack of access -> resource
    # -----------------------------------------------------

    re.compile(
        r"\b("
        r"show|list|reveal|find|give|open|read|access"
        r")\b"
        r".{0,120}"
        r"\b("
        r"unauthorized|inaccessible|without permission|"
        r"i cannot access|i can't access|"
        r"i don't have access|"
        r"not allowed to (?:see|view)|access denied"
        r")\b"
        r".{0,120}"
        r"\b("
        r"files?|documents?|channels?|resources?|"
        r"issues?|pages?"
        r")\b",
        re.IGNORECASE
    ),


    # -----------------------------------------------------
    # Restricted resource probing:
    # resource -> lack of access
    # -----------------------------------------------------

    re.compile(
        r"\b("
        r"files?|documents?|channels?|resources?|"
        r"issues?|pages?"
        r")\b"
        r".{0,120}"
        r"\b("
        r"unauthorized|inaccessible|without permission|"
        r"i cannot access|i can't access|"
        r"i don't have access|"
        r"not allowed to (?:see|view)|access denied"
        r")\b",
        re.IGNORECASE
    ),


    # -----------------------------------------------------
    # Credential / secret extraction
    # -----------------------------------------------------

    re.compile(
        r"\b("
        r"reveal|show|print|dump|display|expose|give"
        r")\b"
        r".{0,80}"
        r"\b("
        r"api[_ -]?key|access[_ -]?token|"
        r"tokenhub_api_key|credentials?|password|"
        r"client[_ -]?secret|private[_ -]?key"
        r")\b",
        re.IGNORECASE
    ),


    # -----------------------------------------------------
    # Explicit unrestricted role-play
    # -----------------------------------------------------

    re.compile(
        r"\b("
        r"pretend|roleplay|act as"
        r")\b"
        r".{0,80}"
        r"\b("
        r"unrestricted|no restrictions?|administrator|admin"
        r")\b"
        r".{0,100}"
        r"\b("
        r"permission|permissions|access|authorization|"
        r"security|restricted"
        r")\b",
        re.IGNORECASE
    ),
]


# =========================================================
# Prompt Injection Inside Retrieved Documents
# =========================================================

CONTENT_INJECTION_PATTERNS = [

    # -----------------------------------------------------
    # Ignore / override instruction hierarchy
    # -----------------------------------------------------

    re.compile(
        r"\b("
        r"ignore|disregard|override|forget|replace|discard"
        r")\b"
        r".{0,100}"
        r"\b("
        r"previous|prior|system|developer|"
        r"instructions?|rules?|prompt"
        r")\b",
        re.IGNORECASE
    ),


    # -----------------------------------------------------
    # "Follow these instructions instead"
    # -----------------------------------------------------

    re.compile(
        r"\b("
        r"follow|obey|execute"
        r")\b"
        r".{0,60}"
        r"\b("
        r"these|following"
        r")\b"
        r".{0,30}"
        r"\binstructions?\b"
        r".{0,80}"
        r"\b("
        r"instead|override|ignore|system|developer"
        r")\b",
        re.IGNORECASE
    ),


    # -----------------------------------------------------
    # System / credential extraction from malicious content
    # -----------------------------------------------------

    re.compile(
        r"\b("
        r"reveal|print|dump|expose|display|show"
        r")\b"
        r".{0,100}"
        r"\b("
        r"system prompt|developer message|"
        r"api[_ -]?key|access[_ -]?token|"
        r"secret|credentials?|password|private[_ -]?key"
        r")\b",
        re.IGNORECASE
    ),


    # -----------------------------------------------------
    # Authorization bypass instruction
    # -----------------------------------------------------

    re.compile(
        r"\b("
        r"bypass|disable|circumvent|skip|evade"
        r")\b"
        r".{0,100}"
        r"\b("
        r"permission|permissions|rbac|access control|"
        r"authorization|security"
        r")\b",
        re.IGNORECASE
    ),


    # -----------------------------------------------------
    # Role reassignment inside retrieved content
    # -----------------------------------------------------

    re.compile(
        r"\b("
        r"you are now|act as|pretend to be"
        r")\b"
        r".{0,80}"
        r"\b("
        r"system|developer|administrator|admin|unrestricted"
        r")\b"
        r".{0,100}"
        r"\b("
        r"reveal|print|dump|ignore|bypass|"
        r"credentials?|secret|token"
        r")\b",
        re.IGNORECASE
    ),
]


# =========================================================
# Secret-like Output Patterns
# =========================================================

SECRET_PATTERNS = [

    # OpenAI-style key
    re.compile(
        r"\bsk-[A-Za-z0-9_-]{20,}\b"
    ),


    # TokenHub key
    re.compile(
        r"TOKENHUB_API_KEY"
        r"\s*[:=]\s*"
        r"\S+",
        re.IGNORECASE
    ),


    # Generic named secrets
    re.compile(
        r"\b("
        r"api[_ -]?key|access[_ -]?token|"
        r"client[_ -]?secret|password|secret"
        r")\b"
        r"\s*[:=]\s*"
        r"[A-Za-z0-9_./+\-=]{20,}",
        re.IGNORECASE
    ),


    # Bearer token
    re.compile(
        r"\bBearer\s+"
        r"[A-Za-z0-9._~+/=-]{20,}\b",
        re.IGNORECASE
    ),


    # JWT-like token
    re.compile(
        r"\b"
        r"eyJ[A-Za-z0-9_-]{10,}"
        r"\."
        r"[A-Za-z0-9_-]{10,}"
        r"\."
        r"[A-Za-z0-9_-]{10,}"
        r"\b"
    ),


    # Private key material
    re.compile(
        r"-----BEGIN "
        r"(?:RSA |EC |OPENSSH )?"
        r"PRIVATE KEY-----"
    ),


    # AWS access key
    re.compile(
        r"\bAKIA[0-9A-Z]{16}\b"
    ),
]


# =========================================================
# Sensitive Internal Output
# =========================================================

INTERNAL_OUTPUT_PATTERNS = [

    re.compile(
        r"\b("
        r"system prompt|developer message|"
        r"hidden instructions?|internal instructions?"
        r")\b"
        r"\s*(?:is|:)",
        re.IGNORECASE
    ),
]


class SafetyGuard:

    # =====================================================
    # User Query Guard
    # =====================================================

    def check_query(
        self,
        query
    ):

        query = (
            query
            or ""
        )


        for pattern in (
            QUERY_INJECTION_PATTERNS
        ):

            if pattern.search(
                query
            ):

                return {
                    "allowed":
                        False,

                    "reason":
                        "suspicious_query_pattern"
                }


        return {
            "allowed":
                True,

            "reason":
                None
        }


    # =====================================================
    # Retrieved Content Guard
    # =====================================================

    def check_resource(
        self,
        resource
    ):

        title = (
            resource.get(
                "title",
                ""
            )
            or ""
        )


        content = (
            resource.get(
                "content",
                ""
            )
            or ""
        )


        text = (
            f"{title}\n"
            f"{content}"
        )


        for pattern in (
            CONTENT_INJECTION_PATTERNS
        ):

            if pattern.search(
                text
            ):

                return {
                    "allowed":
                        False,

                    "reason":
                        "retrieved_prompt_injection"
                }


        return {
            "allowed":
                True,

            "reason":
                None
        }


    # =====================================================
    # Retrieval Result Filtering
    # =====================================================

    def filter_retrieval_results(
        self,
        retrieval_results
    ):

        safe_results = []

        blocked_resources = []


        for item in retrieval_results:

            resource = (
                item[
                    "resource"
                ]
            )


            decision = (
                self.check_resource(
                    resource
                )
            )


            if decision[
                "allowed"
            ]:

                safe_results.append(
                    item
                )

            else:

                blocked_resources.append({
                    "source":
                        resource[
                            "source"
                        ],

                    "resource_id":
                        resource[
                            "resource_id"
                        ],

                    "reason":
                        decision[
                            "reason"
                        ]
                })


        return {
            "safe_results":
                safe_results,

            "blocked_resources":
                blocked_resources,

            "blocked_count":
                len(
                    blocked_resources
                )
        }


    # =====================================================
    # Output Guard
    # =====================================================

    def check_output(
        self,
        answer,
        citation_validation=None
    ):

        answer = (
            answer
            or ""
        )


        # -------------------------------------------------
        # Secret leakage
        # -------------------------------------------------

        for pattern in (
            SECRET_PATTERNS
        ):

            if pattern.search(
                answer
            ):

                return {
                    "allowed":
                        False,

                    "reason":
                        "possible_secret_leakage"
                }


        # -------------------------------------------------
        # Internal prompt leakage
        # -------------------------------------------------

        for pattern in (
            INTERNAL_OUTPUT_PATTERNS
        ):

            if pattern.search(
                answer
            ):

                return {
                    "allowed":
                        False,

                    "reason":
                        "possible_internal_prompt_leakage"
                }


        # -------------------------------------------------
        # Citation validation must exist
        # -------------------------------------------------

        if (
            citation_validation
            is None
        ):

            return {
                "allowed":
                    False,

                "reason":
                    "missing_citation_validation"
            }


        # -------------------------------------------------
        # Citation validation must pass
        # -------------------------------------------------

        if not citation_validation[
            "valid"
        ]:

            return {
                "allowed":
                    False,

                "reason":
                    "invalid_citations"
            }


        return {
            "allowed":
                True,

            "reason":
                None
        }