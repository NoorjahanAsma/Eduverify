from __future__ import annotations
import base64, json, os, time
from pathlib import Path


class LLM:
    provider = "base"

    def __init__(self, model: str, temperature: float = 0.0, timeout: float = 150):
        self.model, self.temperature, self.timeout = model, temperature, timeout
        self.calls: list[dict] = []  # audit log: provider, model, params, timestamp, latency

    def _log(self, t0, **extra):
        self.calls.append(dict(provider=self.provider, model=self.model, temperature=self.temperature,
                               ts=time.strftime("%Y-%m-%dT%H:%M:%S"), latency_s=round(time.time() - t0, 2), **extra))

    def chat(self, prompt: str, images: list[Path] | None = None, system: str | None = None, json_mode: bool = False) -> str:
        raise NotImplementedError


def b64(path) -> str:
    return base64.b64encode(Path(path).read_bytes()).decode()


def _load_env():
    """Read KEY=VALUE lines from the nearest .env (project root); real environment variables win."""
    for d in [Path.cwd(), *Path(__file__).resolve().parents]:
        f = d / ".env"
        if f.is_file():
            for line in f.read_text().splitlines():
                if "=" in line and not line.lstrip().startswith("#"):
                    k, v = line.split("=", 1)
                    os.environ.setdefault(k.strip(), v.strip().strip('"\''))
            return


def get_llm(provider: str, model: str | None = None, **kw) -> LLM:
    _load_env()
    if provider == "ollama":
        from .ollama import Ollama
        return Ollama(model or "qwen3-vl:8b", **kw)
    if provider == "gemini":
        from .gemini import Gemini
        return Gemini(model or "gemini-2.5-flash", **kw)
    if provider == "groq":
        from .groq import Groq
        return Groq(model or "openai/gpt-oss-120b", **kw)
    if provider == "grok":
        from .grok import Grok
        return Grok(model or os.environ.get("XAI_MODEL", "grok-4"), **kw)
    raise ValueError(f"unknown provider {provider!r}")
