# -*- coding: utf-8 -*-
"""VLM-based label extraction (Cowork-quality).

Strategy: give the vision model BOTH the image (for understanding) and the
raw tesseract OCR tokens with precise pixel boxes (for accurate coordinates).
The model then:
  - merges fragments into semantic labels (not raw visual lines),
  - drops noise (stray numbers/marks on product photos, watermarks),
  - translates each label into natural Japanese,
  - returns a precise bounding box composed from the supplied token boxes.

This mirrors what a human does: understand the figure, then place clean,
translated labels using the OCR coordinates.
"""
import os
import json
import base64
import re
from typing import List, Dict, Optional
from openai import OpenAI

SYSTEM = (
    "You read technical infographics and produce clean, translation-ready label "
    "overlays. You translate Simplified Chinese into natural, concise Japanese for "
    "consulting slides, using correct robotics / embodied-AI terminology. You are "
    "precise about geometry and never invent text that is not in the figure."
)

PROMPT = """The attached image is a Chinese technical infographic ({W}x{H} px).
I also give you the raw OCR tokens (pixel boxes, may be fragmented or noisy):

OCR_TOKENS (JSON, pixels): {toks}

Produce a CLEAN set of labels for a Japanese overlay. Rules:
- MERGE OCR fragments that form one logical label into a single entry
  (a heading, OR one "name: value" spec line, OR one short label).
  Keep one entry per visual line; a heading and its description on different
  lines stay as SEPARATE entries. Do NOT over-split a single line.
- DROP noise: stray numbers/marks printed on the product photos, single stray
  characters that are not real labels, source/watermark text, decorative dashes.
- For each label, give bounding box as PERCENT of the image: x,y = top-left
  corner, w,h = width,height. COMPUTE the box from the OCR token boxes you
  merged (convert px->percent). Only if a clearly visible label was missed by
  OCR may you estimate its box from the image.
- TRANSLATE the Chinese into concise natural Japanese. Keep numbers, units and
  Latin acronyms unchanged (DOF, N, kPa, mm, Hz, kg, ℃, cm²...).
- kind: one of "title" | "header" | "label" | "spec".

Return ONLY JSON:
{{"labels":[{{"x":..,"y":..,"w":..,"h":..,"zh":"..","ja":"..","kind":".."}}, ...]}}
x,y,w,h are numbers in percent (0-100)."""


def _client():
    key = os.environ.get("OPENAI_API_KEY")
    if not key:
        raise RuntimeError("OPENAI_API_KEY が未設定です（.env を確認してください）")
    return OpenAI(api_key=key)


def extract_labels(image_path: str, ocr: Dict, model: Optional[str] = None) -> List[Dict]:
    model = model or os.environ.get("OPENAI_VISION_MODEL", "gpt-4o")
    W, H = ocr["width"], ocr["height"]
    toks = []
    for i, l in enumerate(ocr["lines"]):
        toks.append({
            "id": i,
            "x": round(l["x"] / 100 * W), "y": round(l["y"] / 100 * H),
            "w": round(l["w"] / 100 * W), "h": round(l["h"] / 100 * H),
            "text": l["t"],
        })
    with open(image_path, "rb") as f:
        b64 = base64.b64encode(f.read()).decode()
    user = [
        {"type": "text", "text": PROMPT.format(W=W, H=H, toks=json.dumps(toks, ensure_ascii=False))},
        {"type": "image_url", "image_url": {"url": "data:image/jpeg;base64," + b64}},
    ]
    resp = _client().chat.completions.create(
        model=model,
        messages=[{"role": "system", "content": SYSTEM},
                  {"role": "user", "content": user}],
        temperature=0.1,
        response_format={"type": "json_object"},
    )
    content = resp.choices[0].message.content
    try:
        data = json.loads(content)
    except Exception:
        m = re.search(r"\{.*\}", content, flags=re.S)
        data = json.loads(m.group(0)) if m else {"labels": []}
    labels = data.get("labels", data if isinstance(data, list) else [])
    # sanitise
    out = []
    for L in labels:
        try:
            out.append({
                "x": max(0.0, min(100.0, float(L["x"]))),
                "y": max(0.0, min(100.0, float(L["y"]))),
                "w": max(1.0, min(100.0, float(L.get("w", 8)))),
                "h": max(0.5, min(40.0, float(L.get("h", 2)))),
                "zh": str(L.get("zh", "")),
                "ja": str(L.get("ja", L.get("zh", ""))),
                "kind": str(L.get("kind", "label")),
            })
        except (KeyError, ValueError, TypeError):
            continue
    return out
