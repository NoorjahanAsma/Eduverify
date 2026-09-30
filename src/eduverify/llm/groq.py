import os, time, httpx
from . import LLM


class Groq(LLM):
    """Groq API (GROQ_API_KEY), OpenAI-compatible chat completions. Text only (no vision model is offered on the free roster)."""
    provider = "groq"

    def chat(self, prompt, images=None, system=None, json_mode=False):
        key = os.environ.get("GROQ_API_KEY")
        if not key:
            raise RuntimeError("GROQ_API_KEY not set")
        if images:
            raise ValueError("Groq adapter is text-only")
        msgs = ([{"role": "system", "content": system}] if system else []) + [{"role": "user", "content": prompt}]
        body = {"model": self.model, "messages": msgs, "temperature": self.temperature}
        if self.model.startswith("openai/gpt-oss"):
            body["reasoning_effort"] = "low"
        if json_mode:
            body["response_format"] = {"type": "json_object"}
        t0 = time.time()
        for attempt in range(6):
            r = httpx.post("https://api.groq.com/openai/v1/chat/completions", headers={"Authorization": f"Bearer {key}"}, json=body, timeout=self.timeout)
            if r.status_code == 429:  # free-tier rate/token limits: wait as instructed, then retry
                wait = float(r.headers.get("retry-after", 20)) + 1
                if wait > 900:
                    raise RuntimeError(f"Groq daily limit reached, retry after {wait:.0f}s")
                time.sleep(wait); continue
            if r.status_code == 400 and "json_validate_failed" in r.text:  # model produced invalid JSON; let the caller retry
                self._log(t0, usage=None, note="json_validate_failed")
                return r.json().get("error", {}).get("failed_generation", "") or ""
            r.raise_for_status()
            break
        else:
            raise RuntimeError("Groq: repeated 429")
        self._log(t0, usage=r.json().get("usage"))
        return r.json()["choices"][0]["message"]["content"] or ""
