"""Testy nahrávání podkladů: čtení textu ze souborů a vytvoření tématu z podkladů.

Soubory (DOCX, PPTX, PDF) se vytváří přímo v testu v paměti. Skutečné AI se nevolá –
používáme falešné AI z test_learning.py.
"""
import io

import pytest
from docx import Document
from pptx import Presentation
from pptx.util import Inches

from app import documents
from app.documents import DocumentError, extract_text, fit_materials
from tests.test_learning import fake_ai  # noqa: F401  (fixture)

NOTES = (
    "Fotosyntéza probíhá v chloroplastech. Chlorofyl pohlcuje světlo. "
    "Ve světelné fázi vzniká ATP a NADPH, uvolňuje se kyslík. "
    "V Calvinově cyklu se z oxidu uhličitého tvoří glukóza. "
) * 3


def make_docx() -> bytes:
    doc = Document()
    doc.add_heading("Fotosyntéza", 1)
    doc.add_paragraph(NOTES)
    table = doc.add_table(rows=1, cols=2)
    table.rows[0].cells[0].text = "Chlorofyl"
    table.rows[0].cells[1].text = "zelené barvivo"
    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


def make_pptx() -> bytes:
    prs = Presentation()
    slide = prs.slides.add_slide(prs.slide_layouts[1])
    slide.shapes.title.text = "Světelná fáze"
    slide.placeholders[1].text = "Vzniká ATP a NADPH"
    slide.notes_slide.notes_text_frame.text = "Kyslík pochází z vody."
    blank = prs.slides.add_slide(prs.slide_layouts[6])
    box = blank.shapes.add_textbox(Inches(1), Inches(1), Inches(5), Inches(1))
    box.text_frame.text = "Calvinův cyklus"
    buf = io.BytesIO()
    prs.save(buf)
    return buf.getvalue()


def make_pdf(text: str) -> bytes:
    """Nejjednodušší PDF s jednou stránkou a textem (jen ASCII, standardní písmo Helvetica)."""
    stream = f"BT /F1 12 Tf 72 720 Td ({text}) Tj ET".encode()
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R "
        b"/Resources << /Font << /F1 5 0 R >> >> >>",
        b"<< /Length %d >>\nstream\n" % len(stream) + stream + b"\nendstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    out, offsets = io.BytesIO(), []
    out.write(b"%PDF-1.4\n")
    for i, obj in enumerate(objects, 1):
        offsets.append(out.tell())
        out.write(b"%d 0 obj\n" % i + obj + b"\nendobj\n")
    xref = out.tell()
    out.write(b"xref\n0 %d\n0000000000 65535 f \n" % (len(objects) + 1))
    for off in offsets:
        out.write(b"%010d 00000 n \n" % off)
    out.write(b"trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF" % (len(objects) + 1, xref))
    return out.getvalue()


# --- Čtení souborů (documents.py) -----------------------------------------------------------

def test_txt_utf8_a_cp1250():
    assert extract_text("a.txt", "Žluťoučký kůň".encode()) == "Žluťoučký kůň"
    assert extract_text("a.txt", "Žluťoučký kůň".encode("cp1250")) == "Žluťoučký kůň"


def test_docx_vcetne_tabulky():
    text = extract_text("zapisky.docx", make_docx())
    assert "chloroplastech" in text
    assert "Chlorofyl | zelené barvivo" in text


def test_pptx_snimky_a_poznamky():
    text = extract_text("prezentace.pptx", make_pptx())
    assert "[Snímek 1]" in text and "Vzniká ATP a NADPH" in text
    assert "Poznámky: Kyslík pochází z vody." in text
    assert "[Snímek 2]\nCalvinův cyklus" in text


def test_pdf():
    text = extract_text("ucebnice.pdf", make_pdf("Photosynthesis happens in chloroplasts"))
    assert "[Strana 1]" in text and "chloroplasts" in text


@pytest.mark.parametrize(
    "name, data, message",
    [
        ("obrazek.png", b"\x89PNG", "podporované jsou jen"),
        ("stary.doc", b"x", "starém formátu"),
        ("prazdny.txt", b"", "prázdný soubor"),
        ("mezery.txt", b"   \n\n ", "není žádný text"),
        ("rozbity.docx", b"tohle neni docx", "nepodařilo přečíst"),
        ("rozbity.pdf", b"%PDF-1.4 nesmysl", "rozbity.pdf"),
    ],
)
def test_chybne_soubory(name, data, message):
    with pytest.raises(DocumentError) as exc:
        extract_text(name, data)
    assert message in exc.value.message


def test_zkraceni_dlouhych_podkladu():
    short, long = ("kratky.txt", "a" * 100), ("dlouhy.txt", "b\n" * 1000)
    out, truncated = fit_materials([short, long], 500)
    assert truncated
    assert out[0] == short  # krátký soubor zůstane celý
    assert out[1][1].endswith(documents.TRUNCATED_MARK)
    assert sum(len(t) for _, t in out) <= 500 + len(documents.TRUNCATED_MARK) + 1
    assert fit_materials([short], 500) == ([short], False)


# --- API: téma z podkladů -------------------------------------------------------------------

def upload(client, headers, files, title="", level="", skip_entry=False):
    return client.post(
        "/api/subjects/upload",
        data={"title": title, "level": level, "skip_entry": "true" if skip_entry else "false"},
        files=[("files", f) for f in files],
        headers=headers,
    )


DOCX = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


def test_tema_z_podkladu_pouzije_text_podkladu(client, auth_headers, fake_ai):
    r = upload(
        client,
        auth_headers,
        [("zapisky_bio.docx", make_docx(), DOCX), ("doplnek.txt", "Kyslík pochází z vody.".encode(), "text/plain")],
    )
    assert r.status_code == 201, r.text
    subject = r.json()
    assert subject["title"] == "zapisky bio"  # bez názvu se použije název souboru
    assert subject["from_materials"]
    assert [m["filename"] for m in subject["materials"]] == ["zapisky_bio.docx", "doplnek.txt"]

    # AI dostala text obou souborů
    material = fake_ai["plan_material"]
    assert "=== Soubor: zapisky_bio.docx ===" in material and "chloroplastech" in material
    assert "Kyslík pochází z vody." in material

    # výklad i procvičovací test se dělají ze stejných podkladů
    subtopic_id = subject["subtopics"][0]["id"]
    lesson = client.post(f"/api/subtopics/{subtopic_id}/lesson", headers=auth_headers).json()
    assert lesson["from_materials"]
    assert "chloroplastech" in fake_ai["lesson"]["material"]
    r = client.post(f"/api/subtopics/{subtopic_id}/quiz", headers=auth_headers)
    assert r.status_code == 201
    assert "chloroplastech" in fake_ai["quiz"]["material"]


def test_tema_bez_podkladu_je_beze_zmeny(client, auth_headers, fake_ai):
    r = client.post("/api/subjects", json={"title": "Fotosyntéza"}, headers=auth_headers)
    assert r.status_code == 201
    assert r.json()["materials"] == [] and not r.json()["from_materials"]
    assert fake_ai["plan_material"] == ""


def test_nahrani_vlastni_nazev(client, auth_headers, fake_ai):
    r = upload(client, auth_headers, [("a.txt", NOTES.encode(), "text/plain")], title="Biologie – test", level="3. ročník")
    assert r.json()["title"] == "Biologie – test"
    assert fake_ai["plan"] == ("Biologie – test", "3. ročník")
    assert fake_ai["plan_entry_quiz"] is True and r.json()["entry_quiz_id"]


def test_nahrani_bez_vstupniho_testu(client, auth_headers, fake_ai):
    r = upload(client, auth_headers, [("a.txt", NOTES.encode(), "text/plain")], skip_entry=True)
    assert r.status_code == 201, r.text
    assert fake_ai["plan_entry_quiz"] is False
    assert r.json()["entry_skipped"] and r.json()["entry_quiz_id"] is None


def test_nahrani_chyby(client, auth_headers, fake_ai, monkeypatch):
    r = upload(client, auth_headers, [("foto.jpg", b"xx", "image/jpeg")])
    assert r.status_code == 422 and "podporované" in r.json()["detail"]

    r = upload(client, auth_headers, [("malo.txt", "Jen pár slov.".encode(), "text/plain")])
    assert r.status_code == 422 and "málo textu" in r.json()["detail"]

    r = upload(client, auth_headers, [(f"{i}.txt", NOTES.encode(), "text/plain") for i in range(6)])
    assert r.status_code == 422 and "1 až 5" in r.json()["detail"]

    from app.config import get_settings
    monkeypatch.setattr(get_settings(), "max_upload_mb", 0)
    r = upload(client, auth_headers, [("velky.txt", NOTES.encode(), "text/plain")])
    assert r.status_code == 413

    assert "plan" not in fake_ai  # při chybě se AI vůbec nevolala


def test_nahrani_vyzaduje_prihlaseni(client):
    r = upload(client, {}, [("a.txt", NOTES.encode(), "text/plain")])
    assert r.status_code == 401


def test_citat_z_podkladu_se_pripoji_k_vysvetleni():
    from app import ai

    q = ai.AIQuestion(
        subtopic=0, question="Kde probíhá fotosyntéza?", options=["v chloroplastech", "b", "c", "d"],
        correct=0, explanation="Je to v podkladech.", source="„Fotosyntéza probíhá v chloroplastech.“",
    )
    clean = ai._clean_questions([q], 1)[0]
    assert clean.explanation == "Je to v podkladech. V podkladech: „Fotosyntéza probíhá v chloroplastech.“"
