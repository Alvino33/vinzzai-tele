import json
import logging
import os
import re
import subprocess
import threading
from pathlib import Path

DATA_DIR = Path(os.getenv("DATA_DIR", "data"))
USERS_DIR = DATA_DIR / "users"
LEGACY_FILE = DATA_DIR / "materials.jsonl"
_LOCK = threading.Lock()
log = logging.getLogger(__name__)

SUBJECTS = {
    "matematika": {
        "label": "Matematika",
        "aliases": ["matematika", "mtk", "math"],
        "keywords": [
            "matematika", "pecahan", "pembilang", "penyebut", "desimal",
            "persen", "persentase", "keliling", "luas", "volume",
            "bangun datar", "bangun ruang", "sudut", "segitiga", "persegi",
            "persegi panjang", "lingkaran", "kubus", "balok", "bilangan prima",
            "faktor", "kelipatan", "aljabar", "persamaan", "perkalian",
            "pembagian", "penjumlahan", "pengurangan", "diagram", "rata-rata",
        ],
    },
    "ipas": {
        "label": "IPAS",
        "aliases": ["ipas", "ipa", "ilmu pengetahuan alam dan sosial"],
        "keywords": [
            "ipas", "ipa", "ipass", "ekosistem", "fotosintesis", "rantai makanan",
            "jaring-jaring makanan", "tata surya", "planet", "rotasi", "revolusi",
            "gaya", "energi", "listrik", "magnet", "suhu", "kalor", "wujud benda",
            "perubahan wujud", "organ tubuh", "pencernaan", "pernapasan",
            "perkembangbiakan", "hewan", "tumbuhan", "lingkungan", "sumber daya alam",
            "sejarah", "peta", "kenampakan alam", "kegiatan ekonomi", "masyarakat",
        ],
    },
    "bahasa_indonesia": {
        "label": "Bahasa Indonesia",
        "aliases": ["bahasa indonesia", "b indonesia", "bind", "b indo", "indonesia"],
        "keywords": [
            "bahasa indonesia", "ide pokok", "gagasan pokok", "kalimat utama",
            "kalimat penjelas", "teks narasi", "teks deskripsi", "teks prosedur",
            "teks eksplanasi", "puisi", "pantun", "paragraf", "sinonim",
            "antonim", "kata baku", "kata tidak baku", "majas", "tokoh",
            "latar", "amanat", "cerita rakyat", "wawancara", "laporan",
        ],
    },
    "bahasa_inggris": {
        "label": "Bahasa Inggris",
        "aliases": ["bahasa inggris", "b inggris", "bing", "english", "inggris"],
        "keywords": [
            "bahasa inggris", "english", "simple present", "simple past",
            "present tense", "past tense", "verb", "noun", "adjective",
            "pronoun", "adverb", "grammar", "vocabulary", "greeting",
            "introduction", "descriptive text", "recount text", "procedure text",
            "is am are", "was were",
        ],
    },
    "pancasila": {
        "label": "Pendidikan Pancasila",
        "aliases": ["pancasila", "ppkn", "pkn", "pendidikan pancasila"],
        "keywords": [
            "pancasila", "ppkn", "pkn", "undang-undang dasar", "uud 1945",
            "bhinneka tunggal ika", "hak dan kewajiban", "norma", "musyawarah",
            "gotong royong", "garuda pancasila", "sila", "lambang negara",
            "aturan", "keberagaman", "persatuan",
        ],
    },
    "agama": {
        "label": "Pendidikan Agama",
        "aliases": ["agama", "pai", "pendidikan agama", "quran hadits", "alquran"],
        "keywords": [
            "agama", "pai", "alquran", "al-quran", "hadis", "hadits",
            "surah", "surat", "ayat", "tajwid", "iman", "islam",
            "rasul", "nabi", "zakat", "puasa", "salat", "shalat",
            "akhlak", "fiqih", "fikih",
        ],
    },
    "lainnya": {
        "label": "Lainnya",
        "aliases": ["lainnya", "lain-lain", "umum"],
        "keywords": [],
    },
}


def _git_sync_data() -> None:
    """Commit and push the persistent materials directory to the repository."""
    if os.getenv("GITHUB_ACTIONS", "").lower() != "true":
        log.info("Di luar GitHub Actions; perubahan materi hanya disimpan lokal.")
        return

    def git(*args: str) -> subprocess.CompletedProcess:
        return subprocess.run(
            ["git", *args],
            check=True,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=60,
        )

    try:
        git("config", "user.name", "VinAI Bot")
        git("config", "user.email", "41898282+github-actions[bot]@users.noreply.github.com")
        git("add", "-A", str(USERS_DIR))
        staged = subprocess.run(
            ["git", "diff", "--cached", "--quiet", "--", str(USERS_DIR)],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        if staged.returncode == 0:
            return
        if staged.returncode != 1:
            raise RuntimeError(staged.stderr or "Gagal memeriksa perubahan Git.")

        git("commit", "-m", "Simpan/update materi VinAI")
        git("pull", "--rebase", "origin", "main")
        git("push", "origin", "HEAD:main")
        log.info("Materi berhasil disinkronkan ke repository.")
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
        detail = getattr(exc, "stderr", "") or str(exc)
        log.exception("Gagal menyimpan materi ke GitHub: %s", detail)
        raise RuntimeError(
            "Gagal menyimpan materi permanen ke GitHub. Pastikan Actions punya "
            "izin Contents: Read and write, lalu coba lagi."
        ) from exc


def _words(text: str) -> list[str]:
    return re.findall(r"[a-zA-Z0-9À-ÿ]+", text.lower())


def subject_label(subject: str) -> str:
    return SUBJECTS.get(subject, SUBJECTS["lainnya"])["label"]


def resolve_subject(value: str) -> str | None:
    normalized = re.sub(r"[^a-z0-9 ]+", " ", value.lower()).strip()
    for key, config in SUBJECTS.items():
        if normalized == key.replace("_", " ") or normalized == config["label"].lower():
            return key
        if normalized in config["aliases"]:
            return key
    return None


def detect_subject(text: str) -> str:
    normalized = re.sub(r"\s+", " ", text.lower())
    scores = {}
    for key, config in SUBJECTS.items():
        if key == "lainnya":
            continue
        score = 0
        for keyword in config["keywords"]:
            if keyword in normalized:
                score += 3 if " " in keyword else 1
        if score:
            scores[key] = score
    if re.search(r"\d\s*[+×x*/÷=-]\s*\d", normalized):
        scores["matematika"] = scores.get("matematika", 0) + 2
    if not scores:
        return "lainnya"
    return max(scores, key=scores.get)


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


def _subject_file(user_id: int, subject: str) -> Path:
    return USERS_DIR / str(int(user_id)) / f"{subject}.jsonl"


def add_material(user_id: int, title: str, text: str, subject: str | None = None) -> int:
    chunks = _chunks(text)
    if not chunks:
        return 0
    subject = subject if subject in SUBJECTS else detect_subject(f"{title}\n{text}")
    target = _subject_file(user_id, subject)
    target.parent.mkdir(parents=True, exist_ok=True)
    rows = [
        {"user_id": int(user_id), "subject": subject, "title": title[:180], "text": chunk}
        for chunk in chunks
    ]
    with _LOCK, target.open("a", encoding="utf-8") as file:
        for row in rows:
            file.write(json.dumps(row, ensure_ascii=False) + "\n")
        file.flush()
        os.fsync(file.fileno())
        _git_sync_data()
    return len(rows)


def _read_jsonl(path: Path, user_id: int) -> list[dict]:
    rows = []
    if not path.exists():
        return rows
    with path.open("r", encoding="utf-8") as file:
        for line in file:
            try:
                row = json.loads(line)
                if int(row.get("user_id", user_id)) == int(user_id):
                    rows.append(row)
            except (json.JSONDecodeError, TypeError, ValueError):
                continue
    return rows


def _load_user_rows(user_id: int) -> list[dict]:
    rows = []
    user_dir = USERS_DIR / str(int(user_id))
    with _LOCK:
        if user_dir.exists():
            for path in user_dir.glob("*.jsonl"):
                subject = path.stem if path.stem in SUBJECTS else "lainnya"
                for row in _read_jsonl(path, user_id):
                    row.setdefault("subject", subject)
                    rows.append(row)
        for row in _read_jsonl(LEGACY_FILE, user_id):
            row.setdefault("subject", detect_subject(f"{row.get('title', '')}\n{row.get('text', '')}"))
            rows.append(row)
    return rows


def retrieve(user_id: int, question: str, limit: int = 6) -> list[dict]:
    query_words = set(_words(question))
    if not query_words:
        return []
    rows = _load_user_rows(user_id)
    detected = detect_subject(question)
    if detected != "lainnya":
        same_subject = [row for row in rows if row.get("subject") == detected]
        if same_subject:
            rows = same_subject
    scored = []
    for row in rows:
        words = _words(f"{row.get('title', '')} {row.get('text', '')}")
        overlap = query_words & set(words)
        if not overlap:
            continue
        score = sum(1 + min(words.count(word), 3) * 0.15 for word in overlap)
        score += sum(0.5 for word in overlap if len(word) >= 7)
        scored.append((score, row))
    scored.sort(key=lambda item: item[0], reverse=True)
    return [row for _, row in scored[:limit]]


def list_materials(user_id: int, subject: str | None = None) -> list[str]:
    titles, seen = [], set()
    for row in _load_user_rows(user_id):
        if subject and row.get("subject") != subject:
            continue
        title = row.get("title", "Materi tanpa judul")
        if title not in seen:
            seen.add(title)
            titles.append(title)
    return titles


def list_materials_by_subject(user_id: int) -> dict[str, list[str]]:
    grouped = {key: [] for key in SUBJECTS}
    seen = {key: set() for key in SUBJECTS}
    for row in _load_user_rows(user_id):
        subject = row.get("subject", "lainnya")
        if subject not in grouped:
            subject = "lainnya"
        title = row.get("title", "Materi tanpa judul")
        if title not in seen[subject]:
            seen[subject].add(title)
            grouped[subject].append(title)
    return {key: titles for key, titles in grouped.items() if titles}


def clear_materials(user_id: int) -> int:
    removed = 0
    user_dir = USERS_DIR / str(int(user_id))
    with _LOCK:
        if user_dir.exists():
            for path in user_dir.glob("*.jsonl"):
                try:
                    with path.open("r", encoding="utf-8") as file:
                        removed += sum(1 for line in file if line.strip())
                    path.unlink(missing_ok=True)
                except OSError:
                    continue
        if LEGACY_FILE.exists():
            kept = []
            with LEGACY_FILE.open("r", encoding="utf-8") as file:
                for line in file:
                    try:
                        row = json.loads(line)
                        if int(row.get("user_id", -1)) == int(user_id):
                            removed += 1
                        else:
                            kept.append(line)
                    except (json.JSONDecodeError, TypeError, ValueError):
                        kept.append(line)
            temp_file = LEGACY_FILE.with_suffix(".tmp")
            temp_file.write_text("".join(kept), encoding="utf-8")
            temp_file.replace(LEGACY_FILE)
        if user_dir.exists() and not any(user_dir.iterdir()):
            user_dir.rmdir()
        if removed:
            _git_sync_data()
    return removed
