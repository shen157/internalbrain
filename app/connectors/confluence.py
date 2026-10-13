import re
from html import unescape

from app.connectors.base import (
    create_resource
)

from app.data.loader import (
    load_confluence_pages
)


def html_to_text(html_content):

    text = re.sub(
        r"<[^>]+>",
        " ",
        html_content
    )

    text = unescape(text)

    return " ".join(
        text.split()
    )


def convert_confluence_page(page):

    body = page["body"]["value"]

    content = html_to_text(body)

    version = page["version"]

    return create_resource(
        resource_id=page["id"],
        source="confluence",
        resource_type="page",
        title=page["title"],
        content=content,
        updated_at=version["createdAt"],
        source_url=page[
            "_links"
        ].get("webui"),
        metadata={
            "space_id": page["spaceId"],
            "status": page["status"],
            "version_number":
                version["number"],
            "version_message":
                version.get("message"),
            "author_id":
                version.get("authorId")
        }
    )


def load_confluence_resources():

    pages = load_confluence_pages()

    return [
        convert_confluence_page(page)
        for page in pages
    ]