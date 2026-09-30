import os, time, httpx
from . import LLM, b64


class Ollama(LLM):
    provider = "ollama"

    def __init__(self, model, host: str | None = None, **kw):
        super().__init__(model, **kw)
        self.host = host or os.environ.get("OLLAMA_HOST", "http://localhost:11434")

    def chat(self, prompt, images=None, system=None, json_mode=False):
        msgs = ([{"role": "system", "content": system}] if system else [])
        m = {"role": "user", "content": prompt}
        if images:
            m["images"] = [b64(p) for p in images]
        msgs.append(m)
        body = {"model": self.model, "messages": msgs, "stream": False, "think": False,
                "options": {"temperature": self.temperature, "num_ctx": 8192, "num_predict": 2048}}
        # `format: json` returns empty content on qwen3-vl (thinking model), so ask in the prompt and parse leniently.
        if json_mode:
            m["content"] += "\n\nRespond with a single JSON object only, no prose."
        t0 = time.time()
        for attempt in range(4):  # local server can restart/unload between long runs
            try:
                r = httpx.post(f"{self.host}/api/chat", json=body, timeout=self.timeout)
                r.raise_for_status()
                break
            except (httpx.ConnectError, httpx.ReadTimeout, httpx.RemoteProtocolError):
                if attempt == 3:
                    raise
                time.sleep(15 * (attempt + 1))
        self._log(t0, images=len(images or []))
        return r.json()["message"]["content"]
