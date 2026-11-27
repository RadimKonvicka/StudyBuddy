"""Čtení textu z nahraných podkladů (zápisky, prezentace, učebnice).

Podporované formáty: PDF, DOCX (Word), PPTX (PowerPoint), TXT a MD.
Z každého souboru vytáhneme čistý text, který pak dostane AI jako jediný zdroj pro
podtémata, výklad, kartičky a testy. Je to čistý Python bez databáze a bez AI, takže se dá
snadno otestovat.
"""
import io
import re
from pathlib import Path

SUPPORTED = {".pdf", ".docx", ".pptx", ".txt", ".md"}
MIN_CHARS = 200  # méně textu nestačí ani na jeden rozumný test
TRUNCATED_MARK = "[… zbytek souboru se nevešel …]"


class DocumentError(Exception):
    """Soubor nejde přečíst. `message` je česká hláška pro uživatele."""

    def __init__(self, message: str):
        super().__init__(message)
        self.message = message


def _clean(text: str) -> str:
    """Sjednotí konce řádků, odstraní zbytečné mezery a víc než jeden prázdný řádek za sebou."""
    text = text.replace("\r\n", "\n").replace("\r", "\n").replace("\x00", "")
    text = re.sub(r"[ \t ]+", " ", text)
    text = re.sub(r" *\n *", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _pdf(data: bytes) -> str:
    from pypdf import PdfReader
    from pypdf.errors import PdfReadError

    try:
        reader = PdfReader(io.BytesIO(data))
        if reader.is_encrypted:
            reader.decrypt("")  # PDF jen se „zámkem proti úpravám“ jde otevřít bez hesla
        pages = [page.extract_text() or "" for page in reader.pages]
    except (PdfReadError, ValueError, KeyError, TypeError) as err:
        raise DocumentError("PDF soubor je poškozený nebo chráněný heslem.") from err
    return "\n\n".join(f"[Strana {i}]\n{t}" for i, t in enumerate(pages, 1) if t.strip())


def _docx(data: bytes) -> str:
    from docx import Document

    doc = Document(io.BytesIO(data))
    parts = [p.text for p in doc.paragraphs]
    # tabulky (např. přehledy pojmů) – každý řádek jako „buňka | buňka“
    for table in doc.tables:
        for row in table.rows:
            cells = [c.text.strip() for c in row.cells if c.text.strip()]
            if cells:
                parts.append(" | ".join(cells))
    return "\n".join(parts)


def _pptx(data: bytes) -> str:
    from pptx import Presentation

    slides = []
    for i, slide in enumerate(Presentation(io.BytesIO(data)).slides, 1):
        lines = []
        for shape in slide.shapes:
            if shape.has_text_frame:
                lines.extend(p.text for p in shape.text_frame.paragraphs if p.text.strip())
            if getattr(shape, "has_table", False) and shape.has_table:
                for row in shape.table.rows:
                    cells = [c.text.strip() for c in row.cells if c.text.strip()]
                    if cells:
                        lines.append(" | ".join(cells))
        # poznámky řečníka často obsahují to nejdůležitější vysvětlení
        if slide.has_notes_slide and slide.notes_slide.notes_text_frame:
            notes = slide.notes_slide.notes_text_frame.text.strip()
            if notes:
                lines.append(f"Poznámky: {notes}")
        if lines:
            slides.append(f"[Snímek {i}]\n" + "\n".join(lines))
    return "\n\n".join(slides)


def _plain(data: bytes) -> str:
    for encoding in ("utf-8-sig", "cp1250", "latin-1"):  # cp1250 = starší české soubory z Windows
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue
    return ""


def extract_text(filename: str, data: bytes) -> str:
    """Vrátí text souboru, nebo vyhodí DocumentError s českou hláškou."""
    ext = Path(filename).suffix.lower()
    if ext in (".doc", ".ppt"):
        raise DocumentError(f"„{filename}“ je ve starém formátu {ext}. Ulož ho jako {ext}x a nahraj znovu.")
    if ext not in SUPPORTED:
        raise DocumentError(f"„{filename}“: podporované jsou jen soubory PDF, DOCX, PPTX, TXT a MD.")
    if not data:
        raise DocumentError(f"„{filename}“ je prázdný soubor.")

    try:
        if ext == ".pdf":
            text = _pdf(data)
        elif ext == ".docx":
            text = _docx(data)
        elif ext == ".pptx":
            text = _pptx(data)
        else:
            text = _plain(data)
    except DocumentError as err:
        raise DocumentError(f"„{filename}“: {err.message}") from err
    except Exception as err:  # poškozený soubor nebo jiný formát s přejmenovanou koncovkou
        raise DocumentError(f"„{filename}“ se nepodařilo přečíst. Je soubor v pořádku?") from err

    text = _clean(text)
    if not text:
        hint = " Nejspíš je naskenovaný (obsahuje jen obrázky)." if ext == ".pdf" else ""
        raise DocumentError(f"V souboru „{filename}“ není žádný text.{hint}")
    return text


def fit_materials(materials: list[tuple[str, str]], max_chars: int) -> tuple[list[tuple[str, str]], bool]:
    """Zkrátí texty souborů, aby dohromady měly nejvýš `max_chars` znaků.

    Vrátí (seznam (název, text), zkráceno). Krátké soubory zůstanou celé a zbylé místo se rozdělí
    mezi delší soubory, aby se do AI dostal začátek každého souboru, ne jen toho prvního.
    """
    if sum(len(t) for _, t in materials) <= max_chars:
        return materials, False
    limits = {}
    remaining, pending = max_chars, sorted(range(len(materials)), key=lambda i: len(materials[i][1]))
    while pending:
        share = remaining // len(pending)
        i = pending.pop(0)
        limits[i] = min(len(materials[i][1]), share)
        remaining -= limits[i]
    out = []
    for i, (name, text) in enumerate(materials):
        if len(text) > limits[i]:
            text = text[: limits[i]].rsplit("\n", 1)[0] + "\n" + TRUNCATED_MARK
        out.append((name, text))
    return out, True


def format_materials(materials) -> str:
    """Podklady jako jeden text pro AI – každý soubor s nadpisem, aby AI věděla, odkud co je."""
    return "\n\n".join(f"=== Soubor: {name} ===\n{text}" for name, text in materials)
