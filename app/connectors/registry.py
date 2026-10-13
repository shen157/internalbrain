from app.connectors.confluence import (
    load_confluence_resources
)

from app.connectors.jira import (
    load_jira_resources
)

from app.connectors.slack import (
    load_slack_resources
)

from app.connectors.gdrive import (
    load_gdrive_resources
)


def load_all_resources():

    resources = []

    resources.extend(
        load_confluence_resources()
    )

    resources.extend(
        load_jira_resources()
    )

    resources.extend(
        load_slack_resources()
    )

    resources.extend(
        load_gdrive_resources()
    )

    return resources


def build_resource_index(
    resources=None
):

    if resources is None:
        resources = load_all_resources()

    return {
        (
            resource["source"],
            resource["resource_id"]
        ): resource

        for resource in resources
    }


def get_resource(
    source,
    resource_id,
    resources=None
):

    index = build_resource_index(
        resources
    )

    key = (
        source,
        resource_id
    )

    if key not in index:
        raise KeyError(
            f"Resource not found: "
            f"{source}/{resource_id}"
        )

    return index[key]