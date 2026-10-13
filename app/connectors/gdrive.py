from app.connectors.base import (
    create_resource
)

from app.data.loader import (
    load_gdrive_files
)


def convert_gdrive_file(file):

    return create_resource(
        resource_id=file["id"],
        source="gdrive",
        resource_type="file",
        title=file["name"],
        content=(
            file.get("content")
            or ""
        ),
        updated_at=file[
            "modifiedTime"
        ],
        source_url=file.get(
            "webViewLink"
        ),
        metadata={
            "mime_type":
                file["mimeType"],
            "parents":
                file.get(
                    "parents",
                    []
                ),
            "created_at":
                file.get(
                    "createdTime"
                )
        }
    )


def load_gdrive_resources():

    files = load_gdrive_files()

    return [
        convert_gdrive_file(file)
        for file in files
    ]