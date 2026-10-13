REQUIRED_FIELDS = {
    "resource_id",
    "source",
    "resource_type",
    "title",
    "content",
    "updated_at",
    "source_url",
    "metadata"
}


def create_resource(
    resource_id,
    source,
    resource_type,
    title,
    content,
    updated_at,
    source_url=None,
    metadata=None
):
    return {
        "resource_id": resource_id,
        "source": source,
        "resource_type": resource_type,
        "title": title,
        "content": content,
        "updated_at": updated_at,
        "source_url": source_url,
        "metadata": metadata or {}
    }


def validate_resource(resource):
    missing = (
        REQUIRED_FIELDS
        - set(resource.keys())
    )

    if missing:
        raise ValueError(
            f"Missing resource fields: "
            f"{sorted(missing)}"
        )

    return True