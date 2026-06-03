# -*- coding: utf-8 -*-
"""OCR (tesseract chi_sim) -> line clustering -> overlay items.

Returns overlay items in the same schema used by the editor:
  {x,y,w,fs,t, b,a,c,mh, zh}  (percentages relative to image width/height)
"""
import os
from typing import List, Dict
from PIL import Image
import pytesseract

# bundled chi_sim.traineddata lives next to this file under ./tessdata
_HERE = os.path.dirname(os.path.abspath(__file__))
_BUNDLED_TESSDATA = os.path.join(_HERE, "tessdata")

NAVY = "#0f2742"


def _tessdata_prefix() -> str:
    # Prefer bundled chi_sim if present (so the user only needs the tesseract binary)
    if os.path.exists(os.path.join(_BUNDLED_TESSDATA, "chi_sim.traineddata")):
        return _BUNDLED_TESSDATA
    return os.environ.get("TESSDATA_PREFIX", "")


def ocr_lines(image_path: str, lang: str = "chi_sim", min_conf: int = 25) -> List[Dict]:
    """Run OCR and cluster words into lines. Returns list of dicts with
    percentage geometry: x,y (top-left), w,h and the recognised text `t`."""
    prefix = _tessdata_prefix()
    if prefix:
        os.environ["TESSDATA_PREFIX"] = prefix
    im = Image.open(image_path).convert("RGB")
    W, H = im.size
    d = pytesseract.image_to_data(im, lang=lang,
                                  output_type=pytesseract.Output.DICT, config="--psm 11")
    words = []
    for i in range(len(d["text"])):
        t = d["text"][i].strip()
        try:
            conf = int(float(d["conf"][i]))
        except (ValueError, TypeError):
            conf = -1
        if t and conf > min_conf:
            words.append(dict(x=d["left"][i], y=d["top"][i], w=d["width"][i],
                              h=d["height"][i], t=t))
    words.sort(key=lambda r: (r["y"], r["x"]))
    used = [False] * len(words)
    lines = []
    for i, w in enumerate(words):
        if used[i]:
            continue
        cy = w["y"] + w["h"] / 2
        group = [w]
        used[i] = True
        for j in range(len(words)):
            if used[j]:
                continue
            o = words[j]
            ocy = o["y"] + o["h"] / 2
            tol = min(max(10, w["h"] * 0.6), 22)  # cap so tall titles don't swallow nearby rows
            if abs(ocy - cy) < tol:
                gx2 = max(g["x"] + g["w"] for g in group)
                gx1 = min(g["x"] for g in group)
                if o["x"] < gx2 + 45 and o["x"] + o["w"] > gx1 - 45:
                    group.append(o)
                    used[j] = True
        group.sort(key=lambda r: r["x"])
        x1 = min(g["x"] for g in group)
        y1 = min(g["y"] for g in group)
        x2 = max(g["x"] + g["w"] for g in group)
        y2 = max(g["y"] + g["h"] for g in group)
        txt = "".join(g["t"] for g in group)
        lines.append(dict(
            x=round(x1 / W * 100, 2), y=round(y1 / H * 100, 2),
            w=round((x2 - x1) / W * 100, 2), h=round((y2 - y1) / H * 100, 2),
            t=txt,
        ))
    lines.sort(key=lambda r: (r["y"], r["x"]))
    return {"width": W, "height": H, "lines": lines}


HEADER_NAVY = "#103a5c"


def build_items_from_labels(labels: List[Dict], ocr: Dict) -> List[Dict]:
    """Build editor items from VLM semantic labels (Cowork-quality path)."""
    W, H = ocr["width"], ocr["height"]
    items = []
    for L in labels:
        h = float(L.get("h", 2))
        w = float(L.get("w", 8))
        kind = L.get("kind", "label")
        glyph_px = (h / 100 * H) * 0.62
        fs = max(0.6, round(glyph_px / W * 100, 2))
        if kind == "title":
            fs = max(fs, 2.4)
        is_head = kind in ("title", "header")
        items.append(dict(
            x=round(float(L.get("x", 0)), 2), y=round(float(L.get("y", 0)), 2),
            w=round(max(3.0, w), 2), fs=fs,
            t=L.get("ja") or L.get("zh") or "",
            b=1 if is_head else 0,
            a="c" if kind == "title" else "l",
            c=HEADER_NAVY if is_head else NAVY,
            mh=round(h * 0.95, 2), bg=1, zh=L.get("zh", ""),
        ))
    return items


def build_items(ocr: Dict, jp_list: List[str]) -> List[Dict]:
    """Combine OCR geometry with Japanese translations into editor items."""
    W, H = ocr["width"], ocr["height"]
    aspect = H / W if W else 1.5
    items = []
    for line, ja in zip(ocr["lines"], jp_list):
        # font size as % of width, derived from line height (% of height)
        # glyph px ~ line_h_px * 0.62 ; fs% = glyph_px / W * 100
        glyph_px = (line["h"] / 100 * H) * 0.62
        fs = max(0.6, round(glyph_px / W * 100, 2))
        items.append(dict(
            x=line["x"], y=line["y"], w=max(3.0, line["w"]),
            fs=fs, t=ja or line["t"], b=0, a="l", c=NAVY,
            mh=round(line["h"] * 0.95, 2), bg=1, zh=line["t"],
        ))
    return items
