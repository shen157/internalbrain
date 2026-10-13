import os

from dotenv import load_dotenv
from openai import OpenAI


load_dotenv()


DEFAULT_BASE_URL = (
    "https://tokenhub-intl.tencentmaas.com/v1"
)

DEFAULT_MODEL = "hy3"


class LLMClient:

    def __init__(
        self,
        api_key=None,
        base_url=None,
        model=None
    ):

        # ==========================================
        # Configuration
        # ==========================================

        self.api_key = (
            api_key
            or os.getenv(
                "TOKENHUB_API_KEY"
            )
        )

        self.base_url = (
            base_url
            or os.getenv(
                "LLM_BASE_URL"
            )
            or DEFAULT_BASE_URL
        )

        self.model = (
            model
            or os.getenv(
                "LLM_MODEL"
            )
            or DEFAULT_MODEL
        )


        # ==========================================
        # API Key Validation
        # ==========================================

        if not self.api_key:

            raise ValueError(
                "Missing TOKENHUB_API_KEY. "
                "Please add your TokenHub "
                "API Key to the .env file."
            )


        # ==========================================
        # OpenAI-Compatible Client
        # ==========================================

        self.client = OpenAI(
            api_key=self.api_key,
            base_url=self.base_url
        )


    def generate(
        self,
        system_prompt,
        user_prompt,
        temperature=0
    ):

        response = (
            self.client
            .chat
            .completions
            .create(
                model=self.model,

                messages=[
                    {
                        "role":
                            "system",

                        "content":
                            system_prompt
                    },
                    {
                        "role":
                            "user",

                        "content":
                            user_prompt
                    }
                ],

                temperature=temperature,

                stream=False
            )
        )


        answer = (
            response
            .choices[0]
            .message
            .content
        )


        if answer is None:

            return ""


        return answer.strip()