from app.data.loader import (
    load_confluence_space_permissions,
    load_confluence_page_restrictions,
    load_jira_project_roles,
    load_jira_project_permissions,
    load_jira_issue_security,
    load_slack_channels,
    load_slack_channel_members,
    load_gdrive_files,
    load_gdrive_folders,
    load_gdrive_permissions,
    load_gdrive_folder_permissions,
)


class PermissionStore:

    def __init__(self):
        self.reload()


    def reload(self):

        # =================================================
        # Confluence
        # =================================================

        self.confluence_spaces = {
            item["spaceId"]: item
            for item
            in load_confluence_space_permissions()
        }

        self.confluence_pages = {
            item["pageId"]: item
            for item
            in load_confluence_page_restrictions()
        }


        # =================================================
        # Jira
        # =================================================

        self.jira_project_roles = {
            item["projectKey"]: item
            for item
            in load_jira_project_roles()
        }

        self.jira_project_permissions = {
            item["projectKey"]: item
            for item
            in load_jira_project_permissions()
        }

        self.jira_issue_security = {
            item["issueKey"]: item
            for item
            in load_jira_issue_security()
        }


        # =================================================
        # Slack
        # =================================================

        # Channel metadata:
        # public / private
        self.slack_channels = {
            item["id"]: item
            for item
            in load_slack_channels()
        }

        # Channel membership
        self.slack_members = {
            item["channel_id"]: item
            for item
            in load_slack_channel_members()
        }


        # =================================================
        # Google Drive
        # =================================================

        # File metadata:
        # parent folder / inheritance flag
        self.gdrive_files = {
            item["id"]: item
            for item
            in load_gdrive_files()
        }

        # Folder metadata
        self.gdrive_folders = {
            item["id"]: item
            for item
            in load_gdrive_folders()
        }

        # Direct file permissions
        self.gdrive_permissions = {
            item["fileId"]: item
            for item
            in load_gdrive_permissions()
        }

        # Folder permissions
        self.gdrive_folder_permissions = {
            item["folderId"]: item
            for item
            in load_gdrive_folder_permissions()
        }


    # =====================================================
    # Confluence
    # =====================================================

    def get_confluence_space_permission(
        self,
        space_id
    ):
        return self.confluence_spaces.get(
            space_id
        )


    def get_confluence_page_restriction(
        self,
        page_id
    ):
        return self.confluence_pages.get(
            page_id
        )


    # =====================================================
    # Jira
    # =====================================================

    def get_jira_project_roles(
        self,
        project_key
    ):
        return self.jira_project_roles.get(
            project_key
        )


    def get_jira_project_permissions(
        self,
        project_key
    ):
        return self.jira_project_permissions.get(
            project_key
        )


    def get_jira_issue_security(
        self,
        issue_key
    ):
        return self.jira_issue_security.get(
            issue_key
        )


    # =====================================================
    # Slack
    # =====================================================

    def get_slack_channel(
        self,
        channel_id
    ):
        return self.slack_channels.get(
            channel_id
        )


    def get_slack_members(
        self,
        channel_id
    ):

        item = self.slack_members.get(
            channel_id
        )

        if item is None:
            return []

        return item["members"]


    def remove_slack_member(
        self,
        channel_id,
        user_id
    ):

        members = self.get_slack_members(
            channel_id
        )

        if user_id in members:
            members.remove(
                user_id
            )


    def add_slack_member(
        self,
        channel_id,
        user_id
    ):

        members = self.get_slack_members(
            channel_id
        )

        if user_id not in members:
            members.append(
                user_id
            )


    # =====================================================
    # Google Drive
    # =====================================================

    def get_gdrive_file(
        self,
        file_id
    ):
        return self.gdrive_files.get(
            file_id
        )


    def get_gdrive_folder(
        self,
        folder_id
    ):
        return self.gdrive_folders.get(
            folder_id
        )


    def get_gdrive_permissions(
        self,
        file_id
    ):

        item = self.gdrive_permissions.get(
            file_id
        )

        if item is None:
            return []

        return item["permissions"]


    def get_gdrive_folder_permissions(
        self,
        folder_id
    ):

        item = (
            self.gdrive_folder_permissions
            .get(
                folder_id
            )
        )

        if item is None:
            return []

        return item["permissions"]