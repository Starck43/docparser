from pathlib import Path
import docx
from PyPDF2 import PdfReader

from app.services.utils import is_supported


def extract_text_from_txt(path: str) -> str:
    """
    Извлечение текста средствами Python.
    """
    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        return f.read()


def extract_text_from_docx(path: str) -> str:
    """
    Извлечение текста средствами docx.
    """
    doc = docx.Document(path)
    return "\n".join(p.text for p in doc.paragraphs)


def extract_text_from_pdf(path: str) -> str:
    """
    Извлечение текста средствами PyPDF2.
    """
    texts = []
    reader = PdfReader(path)
    for page in reader.pages:
        page_text = page.extract_text()
        if page_text:
            texts.append(page_text)
    return "\n".join(texts).strip()


def parse_file(path: Path) -> str:
    """
    Универсальный парсер: выбирает логику по расширению.
    Возвращает извлечённый текст (может быть пустой строкой).
    """
    if not is_supported(path):
        raise ValueError(f"Формат {path.suffix} не поддерживается")

    suffix = path.suffix.lower()
    path = str(path)

    if suffix in {".txt"}:
        return extract_text_from_txt(path)
    if suffix in {".docx"}:
        return extract_text_from_docx(path)
    if suffix in {".pdf"}:
        return extract_text_from_pdf(path)

    # неизвестный формат — попытка прочитать как текст
    try:
        return extract_text_from_txt(path)
    except Exception:
        return ""
