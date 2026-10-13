import re


STOPWORDS = {
    "a",
    "an",
    "the",
    "and",
    "or",
    "but",
    "if",
    "then",
    "else",
    "when",
    "where",
    "what",
    "which",
    "who",
    "whom",
    "whose",
    "why",
    "how",
    "is",
    "are",
    "was",
    "were",
    "be",
    "been",
    "being",
    "do",
    "does",
    "did",
    "have",
    "has",
    "had",
    "in",
    "on",
    "at",
    "to",
    "for",
    "from",
    "of",
    "with",
    "by",
    "about",
    "into",
    "through",
    "during",
    "before",
    "after",
    "above",
    "below",
    "up",
    "down",
    "out",
    "off",
    "over",
    "under",
    "again",
    "further",
    "this",
    "that",
    "these",
    "those",
    "it",
    "its"
}


def tokenize(text):

    if not text:
        return []

    text = text.lower()

    tokens = re.findall(
        r"[a-z0-9]+(?:-[a-z0-9]+)*",
        text
    )

    tokens = [
        token
        for token in tokens
        if token not in STOPWORDS
    ]

    return tokens


def build_search_text(resource):

    parts = [
        resource.get("title", ""),
        resource.get("content", "")
    ]

    metadata = resource.get(
        "metadata",
        {}
    )

    for value in metadata.values():

        if isinstance(value, str):
            parts.append(value)

        elif isinstance(value, list):

            parts.extend(
                str(item)
                for item in value
            )

    return " ".join(parts)