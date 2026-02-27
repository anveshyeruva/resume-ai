from services.llm.base import LLMProvider

class OpenAIProvider(LLMProvider):
    name = "openai"

    def __init__(self, api_key: str, model: str):
        self.api_key = api_key
        self.model = model

    def generate(self, prompt: str, *, temperature: float = 0.2) -> str:
        # Keep it dependency-light: import only when used
        from openai import OpenAI
        client = OpenAI(api_key=self.api_key)

        resp = client.responses.create(
            model=self.model,
            input=prompt,
            temperature=temperature,
        )
        return resp.output_text.strip()
