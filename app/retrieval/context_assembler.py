class ContextAssembler:

    def __init__(
        self,
        max_chars_per_resource=1200,
        max_total_chars=6000
    ):
        self.max_chars_per_resource = (
            max_chars_per_resource
        )

        self.max_total_chars = (
            max_total_chars
        )


    def _truncate(self, text, max_chars):

        if text is None:
            return ""

        text = str(text).strip()

        if len(text) <= max_chars:
            return text

        return (
            text[:max_chars].rstrip()
            + "..."
        )


    def build(self, retrieval_results):

        if not retrieval_results:
            return {
                "context": "",
                "citations": [],
                "source_count": 0,
                "context_chars": 0
            }


        blocks = []
        citations = []

        used_keys = set()
        total_chars = 0


        for rank, item in enumerate(
            retrieval_results,
            start=1
        ):

            resource = item["resource"]

            key = (
                resource["source"],
                resource["resource_id"]
            )

            # 防止重复资源
            if key in used_keys:
                continue

            used_keys.add(key)


            content = self._truncate(
                resource.get(
                    "content",
                    ""
                ),
                self.max_chars_per_resource
            )


            citation_id = (
                f"S{len(citations) + 1}"
            )


            block = (
                f"[{citation_id}]\n"
                f"Source: "
                f"{resource['source']}\n"
                f"Resource ID: "
                f"{resource['resource_id']}\n"
                f"Title: "
                f"{resource['title']}\n"
                f"Updated At: "
                f"{resource.get('updated_at')}\n"
                f"URL: "
                f"{resource.get('source_url')}\n"
                f"Content:\n"
                f"{content}"
            )


            # 总 context 长度控制
            if (
                total_chars
                + len(block)
                > self.max_total_chars
            ):
                break


            blocks.append(block)

            total_chars += len(block)


            citations.append({
                "citation_id":
                    citation_id,

                "rank":
                    rank,

                "source":
                    resource["source"],

                "resource_id":
                    resource["resource_id"],

                "title":
                    resource["title"],

                "url":
                    resource.get(
                        "source_url"
                    ),

                "updated_at":
                    resource.get(
                        "updated_at"
                    ),

                "retrieval_score":
                    item.get(
                        "score"
                    )
            })


        context = "\n\n---\n\n".join(
            blocks
        )


        return {
            "context":
                context,

            "citations":
                citations,

            "source_count":
                len(citations),

            "context_chars":
                len(context)
        }