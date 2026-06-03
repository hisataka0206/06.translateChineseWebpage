# -*- coding: utf-8 -*-
"""Image Translate Overlay App — FastAPI server.

Flow:  upload image -> OCR(tesseract) + translate(cloud/Ollama) -> editor in
browser -> export PPTX / PNG / HTML.
"""
import os
import io
import json
import uuid
import tempfile
import traceback

from fastapi import FastAPI, UploadFile, File, Form, Request
from fastapi.responses import HTMLResponse, FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from PIL import Image

from dotenv import load_dotenv

import pipeline
import translate as translate_mod
import pptx_export
import vlm

HERE = os.path.dirname(os.path.abspath(__file__))
PARENT = os.path.dirname(HERE)  # translateChineseWebpage/
# load .env (OPENAI_API_KEY etc.) from the parent project
for env in (os.path.join(PARENT, ".env"), os.path.join(HERE, ".env")):
    if os.path.exists(env):
        load_dotenv(env)

SESS_DIR = os.path.join(tempfile.gettempdir(), "image_overlay_app")
os.makedirs(SESS_DIR, exist_ok=True)

app = FastAPI(title="Image Translate Overlay App")
app.mount("/static", StaticFiles(directory=os.path.join(HERE, "static")), name="static")

SESSIONS = {}  # sid -> {"image": path, "items": [...]}


def _tpl(img_src, items, sid, inline_html2canvas=False):
    with open(os.path.join(HERE, "editor_template.html"), encoding="utf-8") as f:
        html = f.read()
    html = (html.replace("__IMG__", img_src)
                .replace("__DATA__", json.dumps(items, ensure_ascii=False))
                .replace("__SID__", sid))
    if inline_html2canvas:
        try:
            with open(os.path.join(HERE, "static", "html2canvas.min.js"), encoding="utf-8") as f:
                js = f.read()
            html = html.replace('<script src="./static/html2canvas.min.js"></script>',
                                "<script>" + js + "</script>")
        except Exception:
            pass
    return html


UPLOAD_PAGE = """<!DOCTYPE html><html lang="ja"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1"><title>画像翻訳オーバーレイ</title>
<style>body{font-family:"Hiragino Sans","Noto Sans JP",sans-serif;background:#eef2f6;color:#16324f;display:flex;justify-content:center;padding:40px}
.card{background:#fff;max-width:560px;width:100%;border-radius:14px;box-shadow:0 8px 30px rgba(0,0,0,.1);padding:28px}
h1{font-size:20px;margin:0 0 4px}p.sub{color:#5b7387;margin:0 0 20px;font-size:13px}
label{display:block;font-weight:bold;margin:14px 0 6px;font-size:13px}
input[type=file],select{width:100%;padding:10px;border:1px solid #c7d3de;border-radius:8px;font-size:14px}
.drop{border:2px dashed #b9c9d6;border-radius:10px;padding:26px;text-align:center;color:#7a8ea0;margin-top:6px}
button{margin-top:22px;width:100%;background:#e67e22;color:#fff;border:none;padding:13px;border-radius:9px;font-size:15px;font-weight:bold;cursor:pointer}
button:hover{background:#f39c12}.note{font-size:12px;color:#7a8ea0;margin-top:14px;line-height:1.5}
#busy{display:none;margin-top:18px;text-align:center;color:#16324f}.sp{display:inline-block;width:16px;height:16px;border:3px solid #ddd;border-top-color:#e67e22;border-radius:50%;animation:r 1s linear infinite;vertical-align:middle;margin-right:8px}@keyframes r{to{transform:rotate(360deg)}}
</style></head><body><div class="card">
<h1>画像翻訳オーバーレイ</h1><p class="sub">中国語の画像 → 日本語の編集可能オーバーレイ（PPTX / PNG / HTML 出力）</p>
<form id="f" action="/process" method="post" enctype="multipart/form-data">
  <label>① 画像ファイル（PNG / JPG）</label>
  <input type="file" name="image" id="img" accept="image/*" required>
  <div class="drop" id="drop">ここにドラッグ＆ドロップも可</div>
  <label>② 解析エンジン</label>
  <select name="provider">
    <option value="cloud">クラウド画像理解（高品質・推奨 / GPT-4o・要 OPENAI_API_KEY）</option>
    <option value="ollama">Ollama ローカル簡易（キー不要・OCR行単位・要 ollama 起動）</option>
  </select>
  <button type="submit">③ 解析して編集画面を開く</button>
  <div id="busy"><span class="sp"></span>OCR・翻訳中です（10〜40秒程度）…</div>
</form>
<div class="note">tesseract（中国語）でOCR → 各行を翻訳 → 位置を合わせて配置します。<br>
編集画面でドラッグ・PowerPoint風ショートカットで微調整 → 上部「出力」から保存。</div>
</div>
<script>
const drop=document.getElementById('drop'),img=document.getElementById('img');
['dragover','dragenter'].forEach(e=>drop.addEventListener(e,ev=>{ev.preventDefault();drop.style.background='#eef7ff';}));
['dragleave','drop'].forEach(e=>drop.addEventListener(e,ev=>{ev.preventDefault();drop.style.background='';}));
drop.addEventListener('drop',ev=>{ if(ev.dataTransfer.files.length){ img.files=ev.dataTransfer.files; drop.textContent=ev.dataTransfer.files[0].name; }});
img.addEventListener('change',()=>{ if(img.files.length) drop.textContent=img.files[0].name; });
document.getElementById('f').addEventListener('submit',()=>{ document.getElementById('busy').style.display='block'; });
</script></body></html>"""


@app.get("/", response_class=HTMLResponse)
def index():
    return UPLOAD_PAGE


@app.post("/process", response_class=HTMLResponse)
async def process(image: UploadFile = File(...), provider: str = Form("cloud")):
    sid = uuid.uuid4().hex[:8]
    raw = await image.read()
    try:
        im = Image.open(io.BytesIO(raw)).convert("RGB")
    except Exception as e:
        return HTMLResponse(_err("画像を読み込めませんでした: " + str(e)))
    img_path = os.path.join(SESS_DIR, sid + ".jpg")
    im.save(img_path, "JPEG", quality=92)
    try:
        ocr = pipeline.ocr_lines(img_path)
        zh = [l["t"] for l in ocr["lines"]]
        if not zh:
            return HTMLResponse(_err("画像から文字を検出できませんでした。別の画像でお試しください。"))
        note = None
        if provider == "cloud":
            # Cowork-quality: VLM understands the image, groups labels, removes
            # noise and translates with context; OCR boxes give precise coords.
            try:
                labels = vlm.extract_labels(img_path, ocr)
                if not labels:
                    raise RuntimeError("ラベルを抽出できませんでした")
                items = pipeline.build_items_from_labels(labels, ocr)
            except Exception as ve:
                # fall back to plain OCR + line translation
                try:
                    ja = translate_mod.translate_lines(zh, provider="cloud")
                except Exception:
                    ja = zh
                items = pipeline.build_items(ocr, ja)
                note = "（高品質解析に失敗したため簡易モードで配置しました: " + str(ve)[:120] + "）"
        else:
            # ollama / offline: OCR + local line translation
            try:
                ja = translate_mod.translate_lines(zh, provider="ollama")
            except Exception as te:
                ja = zh
                note = "（翻訳エンジンに接続できませんでした。原文のまま配置しています: " + str(te)[:120] + "）"
            items = pipeline.build_items(ocr, ja)
        SESSIONS[sid] = {"image": img_path, "items": items}
        body = _tpl("/img/" + sid, items, sid)
        if note:
            body = body.replace("</body>", "<script>setTimeout(()=>alert('"+note.replace("'", "\\'")+"'),400)</script></body>")
        return HTMLResponse(body)
    except Exception:
        return HTMLResponse(_err("解析中にエラーが発生しました:<br><pre>" + traceback.format_exc() + "</pre>"))


def _err(msg):
    return ("<html><head><meta charset='utf-8'></head><body style='font-family:sans-serif;padding:40px;color:#16324f'>"
            "<h2>エラー</h2><p>" + msg + "</p><p><a href='/'>← 戻る</a></p></body></html>")


@app.get("/img/{sid}")
def img(sid: str):
    s = SESSIONS.get(sid)
    if not s:
        return JSONResponse({"error": "session not found"}, status_code=404)
    return FileResponse(s["image"], media_type="image/jpeg")


@app.get("/editor/{sid}", response_class=HTMLResponse)
def editor(sid: str):
    s = SESSIONS.get(sid)
    if not s:
        return HTMLResponse(_err("セッションが見つかりません。"), status_code=404)
    return HTMLResponse(_tpl("/img/" + sid, s["items"], sid))


@app.post("/export/pptx")
async def export_pptx(req: Request):
    data = await req.json()
    sid = data.get("sid"); items = data.get("items", [])
    s = SESSIONS.get(sid)
    if not s:
        return JSONResponse({"error": "session not found"}, status_code=404)
    out = os.path.join(SESS_DIR, sid + ".pptx")
    pptx_export.build_pptx(s["image"], items, out)
    return FileResponse(out, filename="translated_" + sid + ".pptx",
                        media_type="application/vnd.openxmlformats-officedocument.presentationml.presentation")


@app.post("/export/html")
async def export_html(req: Request):
    import base64
    data = await req.json()
    sid = data.get("sid"); items = data.get("items", [])
    s = SESSIONS.get(sid)
    if not s:
        return JSONResponse({"error": "session not found"}, status_code=404)
    with open(s["image"], "rb") as f:
        b64 = base64.b64encode(f.read()).decode()
    html = _tpl("data:image/jpeg;base64," + b64, items, sid, inline_html2canvas=True)
    return Response(content=html, media_type="text/html",
                    headers={"Content-Disposition": "attachment; filename=translated_" + sid + ".html"})


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8765)
