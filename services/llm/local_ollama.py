import requests
from services.llm.base import LLMProvider


class OllamaProvider(LLMProvider):
    name = "ollama"

    def __init__(self, base_url: str, model: str, timeout_s: int = 600, num_predict: int = 220):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout_s = timeout_s
        self.num_predict = num_predict

    def generate(self, prompt: str, *, temperature: float = 0.2, num_predict: int | None = None) -> str:
        url = f"{self.base_url}/api/generate"

        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": temperature,
                "num_predict": int(num_predict if num_predict is not None else self.num_predict),
            },
        }

        r = requests.post(url, json=payload, timeout=self.timeout_s)
        r.raise_for_status()
        data = r.json()
        return (data.get("response") or "").strip()
