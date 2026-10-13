import re


def extract_citation_ids(answer):

    matches = re.findall(
        r"\[(S\d+)\]",
        answer
    )

    return {
        match
        for match in matches
    }


def validate_citations(
    answer,
    citations
):

    available_ids = {
        citation["citation_id"]
        for citation in citations
    }

    used_ids = (
        extract_citation_ids(
            answer
        )
    )


    invalid_ids = (
        used_ids
        - available_ids
    )


    missing_citations = (
        len(used_ids) == 0
    )


    valid = (
        not invalid_ids
        and
        not missing_citations
    )


    return {
        "valid":
            valid,

        "available_ids":
            sorted(
                available_ids
            ),

        "used_ids":
            sorted(
                used_ids
            ),

        "invalid_ids":
            sorted(
                invalid_ids
            ),

        "missing_citations":
            missing_citations
    }