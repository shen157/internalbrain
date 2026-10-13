from app.connectors.base import (
    create_resource
)

from app.data.loader import (
    load_slack_channels,
    load_slack_messages
)


def convert_slack_message(
    message,
    channel
):

    channel_id = channel["id"]

    timestamp = message["ts"]

    resource_id = (
        f"{channel_id}:{timestamp}"
    )

    return create_resource(
        resource_id=resource_id,
        source="slack",
        resource_type="message",
        title=(
            f"#{channel['name']} message"
        ),
        content=message["text"],
        updated_at=timestamp,
        source_url=(
            "https://mock.slack.local/"
            f"{channel_id}/"
            f"{timestamp}"
        ),
        metadata={
            "channel_id":
                channel_id,
            "channel_name":
                channel["name"],
            "is_private":
                channel["is_private"],
            "topic":
                channel.get("topic"),
            "user_id":
                message["user"],
            "thread_ts":
                message.get(
                    "thread_ts"
                ),
            "is_thread_reply":
                message.get(
                    "thread_ts"
                ) is not None
        }
    )


def load_slack_resources():

    channels = {
        channel["id"]: channel
        for channel
        in load_slack_channels()
    }

    messages = load_slack_messages()

    resources = []

    for message in messages:

        channel_id = (
            message["channel_id"]
        )

        channel = channels[
            channel_id
        ]

        resource = (
            convert_slack_message(
                message,
                channel
            )
        )

        resources.append(resource)

    return resources