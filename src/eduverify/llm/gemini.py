import mimetypes, os, time, httpx
from . import LLM, b64


class Gemini(LLM):
    """Google AI Studio key (GEMINI_API_KEY). Antigravity is not a programmatic API."""
    provider = "gemini"

    def chat(self, prompt, images=None, system=None, json_mode=False):
        key = os.environ.get("GEMINI_API_KEY")
        if not key:
            raise RuntimeError("GEMINI_API_KEY not set")
        parts = [{"text": prompt}] + [{"inline_data": {"mime_type": mimetypes.guess_type(str(p))[0] or "image/png", "data": b64(p)}} for p in images or []]
        body = {"contents": [{"role": "user", "parts": parts}],
                "generationConfig": {"temperature": self.temperature}}
        if system:
            body["systemInstruction"] = {"parts": [{"text": system}]}
        if json_mode:
            body["generationConfig"]["responseMimeType"] = "application/json"
        t0 = time.time()
        r = httpx.post(f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent",
                       headers={"x-goog-api-key": key}, json=body, timeout=self.timeout)
        r.raise_for_status()
        self._log(t0, images=len(images or []))
        return r.json()["candidates"][0]["content"]["parts"][0]["text"]
