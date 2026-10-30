import json
import os
import re
import threading
from pathlib import Path

DATA_DIR = Path(os.getenv("DATA_DIR", "data"))
DATA_FILE = DATA_DIR / "materials.jsonl"
_LOCK = threading.Lock()


def _words(text: str) -> list[str]:
    return re.findall(r"[a-zA-Z0-9À-ÿ]+", text.lower())


def _chunks(text: str, size: int = 1100, overlap: int = 160) -> list[str]:
    text = re.sub(r"\s+", " ", text).strip()
    if not text:
        return []
    result = []
    start = 0
    while start < len(text):
        end = min(len(text), start + size)
        if end < len(text):
            boundary = text.rfind(" ", start, end)
            if boundary > start + size // 2:
                end = boundary
        result.append(text[start:end].strip())
        if end >= len(text):
            break
        start = max(end - overlap, start + 1)
    return result


def add_material(user_id: int, title: str, text: str) -> int:
    chunks = _chunks(text)
    if not chunks:
        return 0
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    rows = [
        {"user_id": int(user_id), "title": title[:180], "text": chunk}
        for chunk in chunks
    ]
    with _LOCK, DATA_FILE.open("a", encoding="utf-8") as file:
        for row in rows:
            file.write(json.dumps(row, ensure_ascii=False) + "\n")
    return len(rows)


def _load_user_rows(user_id: int) -> list[dict]:
    if not DATA_FILE.exists():
        return []
    rows = []
    with _LOCK, DATA_FILE.open("r", encoding="utf-8") as file:
        for line in file:
            try:
                row = json.loads(line)
                if int(row.get("user_id", -1)) == int(user_id):
                    rows.append(row)
            except (json.JSONDecodeError, TypeError, ValueError):
                continue
    return rows


def retrieve(user_id: int, question: str, limit: int = 6) -> list[dict]:
    query_words = set(_words(question))
    if not query_words:
        return []
    scored = []
    for row in _load_user_rows(user_id):
        words = _words(row.get("text", ""))
        word_set = set(words)
        overlap = query_words & word_set
        if not overlap:
            continue
        score = sum(1 + min(words.count(word), 3) * 0.15 for word in overlap)
        score += sum(0.5 for word in overlap if len(word) >= 7)
        scored.append((score, row))
    scored.sort(key=lambda item: item[0], reverse=True)
    return [row for _, row in scored[:limit]]


def list_materials(user_id: int) -> list[str]:
    titles = []
    seen = set()
    for row in _load_user_rows(user_id):
        title = row.get("title", "Materi tanpa judul")
        if title not in seen:
            seen.add(title)
            titles.append(title)
    return titles


def clear_materials(user_id: int) -> int:
    if not DATA_FILE.exists():
        return 0
    with _LOCK:
        kept = []
        removed = 0
        with DATA_FILE.open("r", encoding="utf-8") as file:
            for line in file:
                try:
                    row = json.loads(line)
                    if int(row.get("user_id", -1)) == int(user_id):
                        removed += 1
                    else:
                        kept.append(line)
                except (json.JSONDecodeError, TypeError, ValueError):
                    kept.append(line)
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        temp_file = DATA_FILE.with_suffix(".tmp")
        temp_file.write_text("".join(kept), encoding="utf-8")
        temp_file.replace(DATA_FILE)
    return removed
