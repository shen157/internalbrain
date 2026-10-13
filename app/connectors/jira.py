from app.connectors.base import (
    create_resource
)

from app.data.loader import (
    load_jira_issues
)


def convert_jira_issue(issue):

    fields = issue["fields"]

    project = fields["project"]

    status = fields["status"]

    priority = fields.get(
        "priority",
        {}
    )

    issue_type = fields.get(
        "issuetype",
        {}
    )

    assignee = fields.get(
        "assignee"
    )

    reporter = fields.get(
        "reporter"
    )

    return create_resource(
        resource_id=issue["key"],
        source="jira",
        resource_type="issue",
        title=fields["summary"],
        content=(
            fields.get("description")
            or ""
        ),
        updated_at=fields["updated"],
        source_url=(
            "https://mock.jira.local/"
            f"browse/{issue['key']}"
        ),
        metadata={
            "jira_id": issue["id"],
            "project_key":
                project["key"],
            "project_name":
                project["name"],
            "status":
                status["name"],
            "priority":
                priority.get("name"),
            "issue_type":
                issue_type.get("name"),
            "assignee_id":
                (
                    assignee.get(
                        "accountId"
                    )
                    if assignee
                    else None
                ),
            "reporter_id":
                (
                    reporter.get(
                        "accountId"
                    )
                    if reporter
                    else None
                ),
            "labels":
                fields.get(
                    "labels",
                    []
                ),
            "created_at":
                fields.get(
                    "created"
                )
        }
    )


def load_jira_resources():

    issues = load_jira_issues()

    return [
        convert_jira_issue(issue)
        for issue in issues
    ]