import mimetypes, os, time, httpx
from . import LLM, b64


class Grok(LLM):
    """xAI API (XAI_API_KEY), OpenAI-compatible chat completions."""
    provider = "grok"

    def chat(self, prompt, images=None, system=None, json_mode=False):
        key = os.environ.get("XAI_API_KEY")
        if not key:
            raise RuntimeError("XAI_API_KEY not set")
        content = [{"type": "text", "text": prompt}] + [
            {"type": "image_url", "image_url": {"url": f"data:{mimetypes.guess_type(str(p))[0] or 'image/png'};base64,{b64(p)}"}} for p in images or []]
        msgs = ([{"role": "system", "content": system}] if system else []) + [{"role": "user", "content": content}]
        body = {"model": self.model, "messages": msgs, "temperature": self.temperature}
        if json_mode:
            body["response_format"] = {"type": "json_object"}
        t0 = time.time()
        r = httpx.post("https://api.x.ai/v1/chat/completions", headers={"Authorization": f"Bearer {key}"}, json=body, timeout=self.timeout)
        r.raise_for_status()
        self._log(t0, images=len(images or []))
        return r.json()["choices"][0]["message"]["content"]
