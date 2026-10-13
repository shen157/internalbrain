import json
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = PROJECT_ROOT / "data"


def load_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


# =========================================================
# Users / Groups
# =========================================================

def load_users():
    return load_json(DATA_DIR / "users.json")


def load_groups():
    return load_json(DATA_DIR / "groups.json")


# =========================================================
# Confluence
# =========================================================

def load_confluence_pages():
    return load_json(DATA_DIR / "confluence" / "pages.json")


def load_confluence_space_permissions():
    return load_json(
        DATA_DIR / "confluence" / "space_permissions.json"
    )


def load_confluence_page_restrictions():
    return load_json(
        DATA_DIR / "confluence" / "page_restrictions.json"
    )


# =========================================================
# Jira
# =========================================================

def load_jira_issues():
    return load_json(DATA_DIR / "jira" / "issues.json")


def load_jira_project_roles():
    return load_json(
        DATA_DIR / "jira" / "project_roles.json"
    )


def load_jira_project_permissions():
    return load_json(
        DATA_DIR / "jira" / "project_permissions.json"
    )


def load_jira_issue_security():
    return load_json(
        DATA_DIR / "jira" / "issue_security.json"
    )


# =========================================================
# Slack
# =========================================================

def load_slack_channels():
    return load_json(
        DATA_DIR / "slack" / "channels.json"
    )


def load_slack_channel_members():
    return load_json(
        DATA_DIR / "slack" / "channel_members.json"
    )


def load_slack_messages():
    return load_json(
        DATA_DIR / "slack" / "messages.json"
    )


# =========================================================
# Google Drive
# =========================================================

def load_gdrive_files():
    return load_json(
        DATA_DIR / "gdrive" / "files.json"
    )


def load_gdrive_permissions():
    return load_json(
        DATA_DIR / "gdrive" / "permissions.json"
    )

def load_gdrive_folders():
    return load_json(
        DATA_DIR
        / "gdrive"
        / "folders.json"
    )


def load_gdrive_folder_permissions():
    return load_json(
        DATA_DIR
        / "gdrive"
        / "folder_permissions.json"
    )

# =========================================================
# Common Lookup Helper
# =========================================================

def _find_one(items, key, value, label):
    for item in items:
        if item[key] == value:
            return item

    raise KeyError(
        f"{label} not found: {value}"
    )


def get_user(user_id):
    return _find_one(
        load_users(),
        "user_id",
        user_id,
        "User"
    )


def get_group(group_id):
    return _find_one(
        load_groups(),
        "group_id",
        group_id,
        "Group"
    )


def get_confluence_page(page_id):
    return _find_one(
        load_confluence_pages(),
        "id",
        page_id,
        "Confluence page"
    )


def get_jira_issue(issue_key):
    return _find_one(
        load_jira_issues(),
        "key",
        issue_key,
        "Jira issue"
    )


def get_slack_channel(channel_id):
    return _find_one(
        load_slack_channels(),
        "id",
        channel_id,
        "Slack channel"
    )


def get_gdrive_file(file_id):
    return _find_one(
        load_gdrive_files(),
        "id",
        file_id,
        "Google Drive file"
    )