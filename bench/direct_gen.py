"""Generate the `direct` baseline: one image per item straight from a text-to-image model (no spec, no checks).
  --provider sdxl    (run on Colab GPU; needs diffusers, torch)      -> local open baseline
  --provider gemini  (GEMINI_API_KEY; model gemini-2.5-flash-image)  -> API baseline, UNTESTED (no key yet)
  --provider grok    (XAI_API_KEY; grok image endpoint)              -> API baseline, UNTESTED (no key yet)
Writes bench/direct_images/<id>.png. The prompt gives the model the same request + source the spec-based conditions receive."""
import argparse, base64, json, os
from pathlib import Path

ROOT = Path(__file__).parent


def prompt(i):
    return f"{i['request']}\nRender it as a clean educational {i['kind']} with all text readable.\n{i['source']}"


def main():
    p = argparse.ArgumentParser(); p.add_argument("--provider", required=True); p.add_argument("--limit", type=int); a = p.parse_args()
    items = [json.loads(l) for l in open(ROOT / "items.jsonl")]
    if a.limit:
        items = [x for k in ("chart", "diagram") for x in [y for y in items if y["kind"] == k][: a.limit]]
    out = ROOT / "direct_images"; out.mkdir(exist_ok=True)
    if a.provider == "sdxl":
        import torch
        from diffusers import StableDiffusionXLPipeline
        pipe = StableDiffusionXLPipeline.from_pretrained("stabilityai/stable-diffusion-xl-base-1.0", torch_dtype=torch.float16).to("cuda")
        gen = lambda t: pipe(t[:300], num_inference_steps=30, generator=torch.Generator("cuda").manual_seed(0)).images[0]  # CLIP truncates ~77 tokens
        for i in items:
            gen(prompt(i)).save(out / f"{i['id']}.png")
        return
    import httpx
    for i in items:
        if a.provider == "gemini":
            r = httpx.post("https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash-image:generateContent",
                           headers={"x-goog-api-key": os.environ["GEMINI_API_KEY"]}, json={"contents": [{"parts": [{"text": prompt(i)}]}]}, timeout=300).json()
            b = next(p["inlineData"]["data"] for p in r["candidates"][0]["content"]["parts"] if "inlineData" in p)
        else:
            r = httpx.post("https://api.x.ai/v1/images/generations", headers={"Authorization": f"Bearer {os.environ['XAI_API_KEY']}"},
                           json={"model": os.environ.get("XAI_IMAGE_MODEL", "grok-2-image"), "prompt": prompt(i), "response_format": "b64_json"}, timeout=300).json()
            b = r["data"][0]["b64_json"]
        (out / f"{i['id']}.png").write_bytes(base64.b64decode(b))


if __name__ == "__main__":
    main()
