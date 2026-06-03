# -*- coding: utf-8 -*-
"""Batched Chinese -> Japanese translation.

Both providers speak the OpenAI-compatible API:
  - cloud : OpenAI (uses OPENAI_API_KEY)
  - ollama: local server at http://localhost:11434/v1/ (no key needed)

translate_lines() sends ALL lines in a single request and asks for a JSON
array back, so terminology stays consistent and it is fast/cheap.
"""
import os
import json
import re
from typing import List, Optional
from openai import OpenAI

SYSTEM = (
    "You are a professional technical translator specializing in robotics and "
    "humanoid/embodied-AI engineering. Translate Simplified Chinese UI/diagram "
    "labels into natural, concise Japanese suitable for a consulting slide. "
    "Keep numbers, units and Latin acronyms (DOF, N, kPa, mm, Hz...) unchanged. "
    "Do NOT add explanations."
)

PROMPT = (
    "Translate each of the following {n} Chinese lines into Japanese.\n"
    "Return ONLY a JSON array of {n} strings, in the same order, no extra keys.\n"
    "Lines (JSON array):\n{arr}"
)


def _client(provider: str):
    if provider == "ollama":
        base = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434/v1/")
        return OpenAI(api_key="ollama", base_url=base)
    key = os.environ.get("OPENAI_API_KEY")
    if not key:
        raise RuntimeError("OPENAI_API_KEY が未設定です（.env を確認してください）")
    return OpenAI(api_key=key)


def _default_model(provider: str) -> str:
    if provider == "ollama":
        return os.environ.get("OLLAMA_MODEL", "qwen3:8b")
    return os.environ.get("OPENAI_MODEL", "gpt-4o-mini")


def _extract_json_array(text: str) -> List[str]:
    text = text.strip()
    # strip code fences / <think> blocks (qwen)
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.S)
    m = re.search(r"\[.*\]", text, flags=re.S)
    if not m:
        raise ValueError("翻訳結果からJSON配列を抽出できませんでした: " + text[:200])
    return json.loads(m.group(0))


def translate_lines(lines: List[str], provider: str = "cloud",
                    model: Optional[str] = None, batch: int = 60) -> List[str]:
    if not lines:
        return []
    client = _client(provider)
    model = model or _default_model(provider)
    out: List[str] = []
    for i in range(0, len(lines), batch):
        chunk = lines[i:i + batch]
        prompt = PROMPT.format(n=len(chunk), arr=json.dumps(chunk, ensure_ascii=False))
        resp = client.chat.completions.create(
            model=model,
            messages=[{"role": "system", "content": SYSTEM},
                      {"role": "user", "content": prompt}],
            temperature=0.2,
        )
        content = resp.choices[0].message.content
        arr = _extract_json_array(content)
        # pad/trim to chunk length for safety
        arr = [str(x) for x in arr][:len(chunk)]
        while len(arr) < len(chunk):
            arr.append(chunk[len(arr)])
        out.extend(arr)
    return out
