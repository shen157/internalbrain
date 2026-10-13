from app.auth.permission_store import (
    PermissionStore
)


READABLE_DRIVE_ROLES = {
    "owner",
    "writer",
    "commenter",
    "reader"
}


# =========================================================
# Common Helpers
# =========================================================

def has_any_group(
    user_groups,
    allowed_groups
):

    return bool(
        set(user_groups)
        &
        set(allowed_groups)
    )


def matches_user_or_group(
    user,
    allowed_users,
    allowed_groups
):

    user_ok = (
        user["user_id"]
        in allowed_users
    )

    group_ok = has_any_group(
        user["groups"],
        allowed_groups
    )

    return (
        user_ok
        or
        group_ok
    )


def drive_permissions_allow(
    user,
    permissions
):
    """
    Check whether a list of Google Drive
    permission records grants readable
    access to the user.
    """

    for permission in permissions:

        role = permission.get(
            "role"
        )

        if role not in READABLE_DRIVE_ROLES:
            continue


        permission_type = (
            permission.get(
                "type"
            )
        )

        principal = (
            permission.get(
                "principalId"
            )
        )


        # -----------------------------------------
        # Direct user permission
        # -----------------------------------------

        if (
            permission_type
            ==
            "user"
            and
            principal
            ==
            user["user_id"]
        ):
            return True


        # -----------------------------------------
        # Group permission
        # -----------------------------------------

        if (
            permission_type
            ==
            "group"
            and
            principal
            in user["groups"]
        ):
            return True


        # -----------------------------------------
        # Anyone permission
        # -----------------------------------------

        if (
            permission_type
            ==
            "anyone"
        ):
            return True


    return False


# =========================================================
# Permission Engine
# =========================================================

class PermissionEngine:

    def __init__(
        self,
        permission_store=None
    ):

        self.store = (
            permission_store
            if permission_store
            is not None
            else PermissionStore()
        )


    # =====================================================
    # Confluence
    # =====================================================

    def check_confluence(
        self,
        user,
        resource
    ):

        resource_id = (
            resource.get(
                "resource_id"
            )
            or
            resource.get(
                "id"
            )
        )


        metadata = resource.get(
            "metadata",
            {}
        )


        space_id = (
            metadata.get(
                "space_id"
            )
            or
            resource.get(
                "spaceId"
            )
        )


        space_permission = (
            self.store
            .get_confluence_space_permission(
                space_id
            )
        )


        # Fail closed
        if (
            space_permission
            is None
        ):
            return False


        # -----------------------------------------
        # Space-level permission
        # -----------------------------------------

        space_ok = (
            matches_user_or_group(
                user,
                space_permission[
                    "allowedUsers"
                ],
                space_permission[
                    "allowedGroups"
                ]
            )
        )


        if not space_ok:
            return False


        # -----------------------------------------
        # Page-level restriction
        # -----------------------------------------

        page_restriction = (
            self.store
            .get_confluence_page_restriction(
                resource_id
            )
        )


        # No page restriction record
        if (
            page_restriction
            is None
        ):
            return True


        restrictions = (
            page_restriction[
                "readRestrictions"
            ]
        )


        allowed_users = (
            restrictions[
                "users"
            ]
        )

        allowed_groups = (
            restrictions[
                "groups"
            ]
        )


        # Empty restriction means:
        # no additional restriction.
        if (
            not allowed_users
            and
            not allowed_groups
        ):
            return True


        return matches_user_or_group(
            user,
            allowed_users,
            allowed_groups
        )


    # =====================================================
    # Jira
    # =====================================================

    def check_jira(
        self,
        user,
        resource
    ):

        resource_id = (
            resource.get(
                "resource_id"
            )
            or
            resource.get(
                "key"
            )
        )


        metadata = resource.get(
            "metadata",
            {}
        )


        project_key = (
            metadata.get(
                "project_key"
            )
        )


        # Raw Jira issue fallback
        if project_key is None:

            fields = (
                resource.get(
                    "fields",
                    {}
                )
            )

            project = (
                fields.get(
                    "project",
                    {}
                )
            )

            project_key = (
                project.get(
                    "key"
                )
            )


        role_data = (
            self.store
            .get_jira_project_roles(
                project_key
            )
        )


        permission_data = (
            self.store
            .get_jira_project_permissions(
                project_key
            )
        )


        # Fail closed
        if (
            role_data is None
            or
            permission_data is None
        ):
            return False


        # -----------------------------------------
        # Find user's Jira project roles
        # -----------------------------------------

        user_roles = set()


        for role in role_data[
            "roles"
        ]:

            direct_user = (
                user["user_id"]
                in role[
                    "users"
                ]
            )


            group_member = (
                has_any_group(
                    user[
                        "groups"
                    ],
                    role[
                        "groups"
                    ]
                )
            )


            if (
                direct_user
                or
                group_member
            ):
                user_roles.add(
                    role[
                        "name"
                    ]
                )


        # -----------------------------------------
        # Browse Project permission
        # -----------------------------------------

        browse_roles = set()


        for permission in (
            permission_data[
                "permissions"
            ]
        ):

            if (
                permission[
                    "permission"
                ]
                ==
                "BROWSE_PROJECTS"
            ):

                browse_roles = set(
                    permission[
                        "roles"
                    ]
                )

                break


        browse_ok = bool(
            user_roles
            &
            browse_roles
        )


        if not browse_ok:
            return False


        # -----------------------------------------
        # Issue-level Security
        # -----------------------------------------

        security = (
            self.store
            .get_jira_issue_security(
                resource_id
            )
        )


        # No issue security restriction
        if security is None:
            return True


        level = (
            security[
                "securityLevel"
            ]
        )


        return matches_user_or_group(
            user,
            level[
                "allowedUsers"
            ],
            level[
                "allowedGroups"
            ]
        )


    # =====================================================
    # Slack
    # =====================================================

    def check_slack(
        self,
        user,
        resource
    ):

        metadata = resource.get(
            "metadata",
            {}
        )


        channel_id = (
            metadata.get(
                "channel_id"
            )
            or
            resource.get(
                "id"
            )
            or
            resource.get(
                "channel_id"
            )
        )


        channel = (
            self.store
            .get_slack_channel(
                channel_id
            )
        )


        # -----------------------------------------
        # Unknown channel → fail closed
        # -----------------------------------------

        if channel is None:
            return False


        # -----------------------------------------
        # Public channel
        #
        # Any authenticated enterprise user
        # can read a public channel.
        # -----------------------------------------

        if not channel.get(
            "is_private",
            False
        ):
            return True


        # -----------------------------------------
        # Private channel
        #
        # Explicit channel membership required.
        # -----------------------------------------

        members = (
            self.store
            .get_slack_members(
                channel_id
            )
        )


        return (
            user["user_id"]
            in members
        )


    # =====================================================
    # Google Drive
    # =====================================================

    def check_gdrive(
        self,
        user,
        resource
    ):

        resource_id = (
            resource.get(
                "resource_id"
            )
            or
            resource.get(
                "id"
            )
        )


        # Fail closed
        if resource_id is None:
            return False


        # =================================================
        # A. Folder access
        # =================================================

        folder = (
            self.store
            .get_gdrive_folder(
                resource_id
            )
        )


        if folder is not None:

            folder_permissions = (
                self.store
                .get_gdrive_folder_permissions(
                    resource_id
                )
            )


            return (
                drive_permissions_allow(
                    user,
                    folder_permissions
                )
            )


        # =================================================
        # B. File access
        # =================================================

        file_data = (
            self.store
            .get_gdrive_file(
                resource_id
            )
        )


        # Unknown file → fail closed
        if file_data is None:
            return False


        # -----------------------------------------
        # 1. Direct file permission
        # -----------------------------------------

        direct_permissions = (
            self.store
            .get_gdrive_permissions(
                resource_id
            )
        )


        if drive_permissions_allow(
            user,
            direct_permissions
        ):
            return True


        # -----------------------------------------
        # 2. Check whether inheritance is disabled
        #
        # Missing flag defaults to True.
        # -----------------------------------------

        if (
            file_data.get(
                "inherit_permissions",
                True
            )
            is False
        ):
            return False


        # -----------------------------------------
        # 3. Resolve parent folder
        # -----------------------------------------

        parent_folder_id = (
            file_data.get(
                "parent_folder_id"
            )
        )


        # API-style fallback:
        # parents = ["FOLDER-XXX"]
        if parent_folder_id is None:

            parents = (
                file_data.get(
                    "parents",
                    []
                )
            )

            if parents:
                parent_folder_id = (
                    parents[0]
                )


        # No parent folder
        if parent_folder_id is None:
            return False


        # -----------------------------------------
        # 4. Validate folder exists
        # -----------------------------------------

        parent_folder = (
            self.store
            .get_gdrive_folder(
                parent_folder_id
            )
        )


        if parent_folder is None:
            return False


        # -----------------------------------------
        # 5. Inherit folder permission
        # -----------------------------------------

        folder_permissions = (
            self.store
            .get_gdrive_folder_permissions(
                parent_folder_id
            )
        )


        return drive_permissions_allow(
            user,
            folder_permissions
        )


    # =====================================================
    # Unified Entry Point
    # =====================================================

    def can_access(
        self,
        user,
        resource,
        source=None
    ):

        source = (
            source
            or
            resource.get(
                "source"
            )
        )


        if source == "confluence":

            return (
                self.check_confluence(
                    user,
                    resource
                )
            )


        if source == "jira":

            return (
                self.check_jira(
                    user,
                    resource
                )
            )


        if source == "slack":

            return (
                self.check_slack(
                    user,
                    resource
                )
            )


        if source == "gdrive":

            return (
                self.check_gdrive(
                    user,
                    resource
                )
            )


        raise ValueError(
            f"Unknown source: {source}"
        )


# =========================================================
# Default Shared Engine
# =========================================================

DEFAULT_PERMISSION_STORE = (
    PermissionStore()
)


DEFAULT_PERMISSION_ENGINE = (
    PermissionEngine(
        DEFAULT_PERMISSION_STORE
    )
)


def can_access(
    user,
    resource,
    source=None
):

    return (
        DEFAULT_PERMISSION_ENGINE
        .can_access(
            user,
            resource,
            source
        )
    )