"""
word_export.py  —  Generador de .docx para el SRS dinámico de Anémona/Banorte

Robustez ante datos reales de Firestore:
- Valores "NULL" (string literal) → tratados como vacío
- null / None → vacío
- Arrays en campos (ej: AREAS_IMPACTADAS) → unidos con ", "
- Campos extra en w_000 → filas adicionales automáticas
- Múltiples widgets del mismo tipo (varios w_001) → todos se renderizan
- Widgets en cualquier orden (se re-ordenan por posicion)
"""

import io
import os
from typing import Any

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn
from docx.oxml import OxmlElement
from docx.shared import Pt, RGBColor, Inches
from docx.enum.table import WD_TABLE_ALIGNMENT


AZUL_BANORTE = RGBColor(0x13, 0x3B, 0x73)
ROJO_BANORTE = RGBColor(0xEB, 0x00, 0x29)
AZUL_TEXTO   = RGBColor(0x1D, 0x5D, 0xA8)
GRIS_LABEL   = RGBColor(0x7C, 0x7C, 0x7C)
BLANCO       = RGBColor(0xFF, 0xFF, 0xFF)


# ─── Normalización ───────────────────────────────────────────────────────────

def _val(v: Any) -> str:
    if v is None:
        return ""
    if isinstance(v, list):
        return ", ".join(_val(i) for i in v)
    s = str(v).strip()
    return "" if s.upper() == "NULL" else s


# ─── Helpers de estilo ───────────────────────────────────────────────────────

def _font(run, size_pt: float, bold=False, italic=False, color: RGBColor = None):
    run.font.name = "Arial"
    run.font.size = Pt(size_pt)
    run.font.bold = bold
    run.font.italic = italic
    if color:
        run.font.color.rgb = color


def _para(container, text="", size=11, bold=False, italic=False,
          color=None, before=0, after=6, align=WD_ALIGN_PARAGRAPH.LEFT):
    p = container.add_paragraph()
    p.alignment = align
    p.paragraph_format.space_before = Pt(before)
    p.paragraph_format.space_after  = Pt(after)
    if text:
        r = p.add_run(text)
        _font(r, size, bold=bold, italic=italic, color=color)
    return p


def _cell_bg(cell, hex6: str):
    tc   = cell._tc
    tcPr = tc.get_or_add_tcPr()
    shd  = OxmlElement("w:shd")
    shd.set(qn("w:val"),   "clear")
    shd.set(qn("w:color"), "auto")
    shd.set(qn("w:fill"),  hex6)
    tcPr.append(shd)


def _border_top(p, color_hex="000000", size=12):
    pPr  = p._p.get_or_add_pPr()
    pBdr = OxmlElement("w:pBdr")
    top  = OxmlElement("w:top")
    top.set(qn("w:val"),   "single")
    top.set(qn("w:sz"),    str(size))
    top.set(qn("w:space"), "4")
    top.set(qn("w:color"), color_hex)
    pBdr.append(top)
    pPr.append(pBdr)


def _spacer(doc):
    _para(doc, after=2)


# ─── Componentes UI ──────────────────────────────────────────────────────────

def _section_line(doc, number: str, title: str, optional=True):
    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(14)
    p.paragraph_format.space_after  = Pt(4)
    _border_top(p)
    r1 = p.add_run(f"{number}  ")
    _font(r1, 13, bold=True)
    r2 = p.add_run(title)
    _font(r2, 13, bold=True)
    if optional:
        r3 = p.add_run("   (Opcional)")
        _font(r3, 9, color=ROJO_BANORTE)


def _subsection_line(doc, number: str, title: str):
    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(10)
    p.paragraph_format.space_after  = Pt(4)
    r = p.add_run(f"{number}  {title}.")
    _font(r, 13, bold=True)


# ─── Intro ───────────────────────────────────────────────────────────────────

INTRO = (
    "Este cuestionario tiene como propósito conocer cuáles son los beneficios, costos y riesgos "
    "relacionados con cada iniciativa que ingresa al portafolio de proyectos y mantenimientos "
    "tecnológicos de Áreas de Soporte. Esta información será de utilidad para ponderar el "
    "portafolio en su conjunto y priorizar la atención de los requerimientos de acuerdo a su "
    "beneficio económico, alineación estratégica y conveniencia de su realización."
)

def _add_intro(doc):
    _para(doc, INTRO, size=11, after=12)


# ─── W000 ────────────────────────────────────────────────────────────────────

W000_BASE = [
    "SOLICITANTE", "INFO_CONTACTO", "DGA", "PATROCINADOR",
    "CR", "SOCIO", "NOMBRE_INICIATIVA", "TIPO_INICIATIVA",
]

def _render_w000(doc, widget: dict):
    campos = widget.get("campos", {}) or {}
    desc   = widget.get("descripcion_campos", {}) or {}

    base_keys  = [k for k in W000_BASE if k in campos]
    extra_keys = [k for k in campos if k not in W000_BASE]
    all_keys   = base_keys + extra_keys
    if not all_keys:
        return

    tbl = doc.add_table(rows=len(all_keys), cols=2)
    tbl.style     = "Table Grid"
    tbl.alignment = WD_TABLE_ALIGNMENT.LEFT

    for i, key in enumerate(all_keys):
        row   = tbl.rows[i]
        label = desc.get(key) or key.replace("_", " ").title()
        valor = _val(campos.get(key))

        row.cells[0].width = Inches(2.6)
        row.cells[1].width = Inches(4.9)

        r0 = row.cells[0].paragraphs[0].add_run(label)
        _font(r0, 11, bold=True)

        r1 = row.cells[1].paragraphs[0].add_run(valor)
        _font(r1, 11)

    _spacer(doc)


# ─── W001 ────────────────────────────────────────────────────────────────────

def _render_w001(doc, widget: dict):
    campos = widget.get("campos", {}) or {}
    pos    = widget.get("posicion", "")
    desc   = widget.get("descripcion_campos", {}) or {}

    titulo      = _val(campos.get("titulo")) or widget.get("titulo", "")
    subtitulo   = _val(campos.get("subtitulo", ""))
    descripcion = _val(campos.get("descripcion", ""))

    _section_line(doc, f"{pos}.", titulo, optional=True)

    if subtitulo:
        _para(doc, subtitulo, size=11, bold=True, after=4)
    if descripcion:
        _para(doc, descripcion, size=11, italic=True, color=AZUL_TEXTO, after=8)

    skip = {"titulo", "subtitulo", "descripcion"}
    for key, valor in campos.items():
        if key in skip:
            continue
        v = _val(valor)
        if not v:
            continue
        label = desc.get(key, key.replace("_", " ").title())
        p  = doc.add_paragraph()
        r1 = p.add_run(f"{label}: ")
        _font(r1, 11, bold=True)
        r2 = p.add_run(v)
        _font(r2, 11)
        p.paragraph_format.space_after = Pt(4)

    _spacer(doc)


# ─── W002 ────────────────────────────────────────────────────────────────────

def _render_w002(doc, widget: dict):
    campos = widget.get("campos", {}) or {}
    pos    = widget.get("posicion", "")

    titulo     = _val(campos.get("Titulo")) or widget.get("titulo", "Objetivos de la iniciativa")
    sec1t      = _val(campos.get("Seccion_1Titulo", ""))
    sec1x      = _val(campos.get("Seccion_1", ""))
    sec2t      = _val(campos.get("Seccion_2Titulo", ""))
    sec2x      = _val(campos.get("Seccion_2", ""))

    _section_line(doc, f"{pos}.", titulo, optional=True)

    for st, sx in [(sec1t, sec1x), (sec2t, sec2x)]:
        if st:
            _para(doc, st, size=11, bold=True, after=2)
        if sx:
            _para(doc, sx, size=11, italic=True, color=AZUL_TEXTO, after=8)

    _spacer(doc)


# ─── W003 ────────────────────────────────────────────────────────────────────

def _render_w003(doc, widget: dict):
    campos  = widget.get("campos", {}) or {}
    pos     = widget.get("posicion", "")
    titulo  = _val(campos.get("titulo")) or widget.get("titulo", "")
    headers = campos.get("headers") or [
        {"key": "TIPO",             "label": "Riesgo"},
        {"key": "PROBABLE_PERDIDA", "label": "Probable Pérdida"},
        {"key": "JUSTIFICACION",    "label": "Justificación"},
    ]
    filas = campos.get("filas") or []

    _subsection_line(doc, str(pos), titulo)

    num_cols = len(headers)
    tbl = doc.add_table(rows=1 + max(len(filas), 1), cols=num_cols)
    tbl.style     = "Table Grid"
    tbl.alignment = WD_TABLE_ALIGNMENT.LEFT

    # Header azul
    hrow = tbl.rows[0]
    for i, h in enumerate(headers):
        cell = hrow.cells[i]
        _cell_bg(cell, "133b73")
        p = cell.paragraphs[0]
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        r = p.add_run(_val(h.get("label", "")))
        _font(r, 11, bold=True, color=BLANCO)

    if filas:
        for ri, fila in enumerate(filas):
            row = tbl.rows[ri + 1]
            for ci, h in enumerate(headers):
                r = row.cells[ci].paragraphs[0].add_run(_val(fila.get(h["key"], "")))
                _font(r, 11)
    else:
        merged = tbl.rows[1].cells[0].merge(tbl.rows[1].cells[-1])
        p = merged.paragraphs[0]
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        r = p.add_run("N/A")
        _font(r, 11, color=GRIS_LABEL)

    _spacer(doc)


# ─── W005 ────────────────────────────────────────────────────────────────────

def _render_w005(doc, widget: dict):
    campos = widget.get("campos", {}) or {}
    pos    = widget.get("posicion", "")
    titulo = _val(campos.get("titulo")) or widget.get("titulo", "")
    filas  = campos.get("filas") or []

    _subsection_line(doc, str(pos), titulo)

    if not filas:
        _spacer(doc)
        return

    max_cols = max((len(f.get("celdas", [])) for f in filas), default=1)

    tbl = doc.add_table(rows=len(filas), cols=max_cols)
    tbl.style = "Table Grid"
    tbl.alignment = WD_TABLE_ALIGNMENT.LEFT

    for ri, fila in enumerate(filas):
        celdas = fila.get("celdas", [])
        row = tbl.rows[ri]

        # Si la fila solo tiene una celda, se combina toda la fila
        if len(celdas) == 1 and max_cols > 1:
            cell = row.cells[0].merge(row.cells[-1])
            cel = celdas[0]

            label = _val(cel.get("label", ""))
            valor = _val(cel.get("valor", ""))
            bold  = bool(cel.get("bold", False))

            texto = valor or label

            p = cell.paragraphs[0]
            r = p.add_run(texto)
            _font(r, 11, bold=bold)

            continue

        # Filas normales con varias columnas
        for ci in range(max_cols):
            cell = row.cells[ci]

            if ci >= len(celdas):
                continue

            cel   = celdas[ci]
            label = _val(cel.get("label", ""))
            valor = _val(cel.get("valor", ""))
            bold  = bool(cel.get("bold", False))

            if label and valor:
                rl = cell.paragraphs[0].add_run(label)
                _font(rl, 9, color=GRIS_LABEL)

                rv = cell.add_paragraph().add_run(valor)
                _font(rv, 11, bold=bold)

            else:
                texto = valor or label
                r = cell.paragraphs[0].add_run(texto)
                _font(r, 11, bold=bold, color=GRIS_LABEL if not bold else None)

    _spacer(doc)

# ─── W004 / WChart ───────────────────────────────────────────────────────────

def _render_wchart(doc, widget: dict):
    campos = widget.get("campos", {}) or {}
    pos    = widget.get("posicion", "")
    titulo = _val(campos.get("titulo")) or widget.get("titulo", "Gráfica")
    pie    = _val(campos.get("pie", ""))
    unidad = _val(campos.get("unidad", ""))
    barras = campos.get("barras") or []

    _section_line(doc, f"{pos}.", titulo, optional=False)

    if not barras:
        _para(doc, "Sin datos de gráfica.", size=11, italic=True, color=GRIS_LABEL)
        _spacer(doc)
        return

    col2 = f"Valor ({unidad})" if unidad else "Valor"
    tbl  = doc.add_table(rows=1 + len(barras), cols=2)
    tbl.style     = "Table Grid"
    tbl.alignment = WD_TABLE_ALIGNMENT.LEFT

    for i, lbl in enumerate(["Categoría", col2]):
        cell = tbl.rows[0].cells[i]
        _cell_bg(cell, "133b73")
        p = cell.paragraphs[0]
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        r = p.add_run(lbl)
        _font(r, 11, bold=True, color=BLANCO)

    for i, barra in enumerate(barras):
        row = tbl.rows[i + 1]
        r0  = row.cells[0].paragraphs[0].add_run(_val(barra.get("etiqueta", "")))
        _font(r0, 11)
        p1  = row.cells[1].paragraphs[0]
        p1.alignment = WD_ALIGN_PARAGRAPH.CENTER
        r1  = p1.add_run(_val(barra.get("valor", "")))
        _font(r1, 11)

    if pie:
        _para(doc, pie, size=9, italic=True, color=GRIS_LABEL, before=4)

    _spacer(doc)


# ─── Header / Footer ─────────────────────────────────────────────────────────

_IMG_RAYA   = "public/images/rayaNegra.png"
_IMG_FOOTER = "public/images/banortegf.png"

def _add_header(doc):
    sec    = doc.sections[0]
    header = sec.header
    header.is_linked_to_previous = False

    # Limpiar párrafo default
    for p in header.paragraphs:
        p.clear()

    # Tabla de 2 celdas: texto | imagen
    tbl = header.add_table(rows=1, cols=2, width=Inches(6.5))
    tbl.alignment = WD_TABLE_ALIGNMENT.LEFT

    # Celda izquierda — texto
    cell_left  = tbl.cell(0, 0)
    cell_right = tbl.cell(0, 1)

    cell_left.width  = Inches(3.5)
    cell_right.width = Inches(3.0)

    # Sin bordes en la tabla
    for cell in [cell_left, cell_right]:
        tc   = cell._tc
        tcPr = tc.get_or_add_tcPr()
        tcBdr = OxmlElement("w:tcBdr")
        for side in ["top", "left", "bottom", "right"]:
            border = OxmlElement(f"w:{side}")
            border.set(qn("w:val"), "none")
            tcBdr.append(border)
        tcPr.append(tcBdr)

    p_left = cell_left.paragraphs[0]
    p_left.paragraph_format.space_before = Pt(0)
    p_left.paragraph_format.space_after  = Pt(0)
    r1 = p_left.add_run("Formato Estándar | ")
    _font(r1, 11, bold=True, color=GRIS_LABEL)
    r2 = p_left.add_run("Levantamiento de Requerimiento")
    _font(r2, 11, color=GRIS_LABEL)

    # Celda derecha — imagen alineada a la derecha
    p_right = cell_right.paragraphs[0]
    p_right.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    p_right.paragraph_format.space_before = Pt(0)
    p_right.paragraph_format.space_after  = Pt(0)
    if os.path.exists(_IMG_RAYA):
        r_img = p_right.add_run()
        r_img.add_picture(_IMG_RAYA, width=Inches(2.8), height=Inches(0.4))

    # Borde inferior debajo de la tabla
    p_after = header.add_paragraph()
    p_after.paragraph_format.space_before = Pt(2)
    p_after.paragraph_format.space_after  = Pt(0)
    pPr  = p_after._p.get_or_add_pPr()
    pBdr = OxmlElement("w:pBdr")
    bot  = OxmlElement("w:bottom")
    bot.set(qn("w:val"),   "single")
    bot.set(qn("w:sz"),    "6")
    bot.set(qn("w:space"), "4")
    bot.set(qn("w:color"), "b9a89f")
    pBdr.append(bot)
    pPr.append(pBdr)

def _add_footer(doc):
    sec    = doc.sections[0]
    footer = sec.footer
    footer.is_linked_to_previous = False

    for p in footer.paragraphs:
        p.clear()

    p = footer.paragraphs[0] if footer.paragraphs else footer.add_paragraph()

    p.alignment = WD_ALIGN_PARAGRAPH.LEFT
    p.paragraph_format.space_before = Pt(0)
    p.paragraph_format.space_after  = Pt(0)

    if os.path.exists(_IMG_FOOTER):
        r_img = p.add_run()
        r_img.add_picture(_IMG_FOOTER, height=Inches(0.45))
    else:
        r = p.add_run("GRUPO FINANCIERO BANORTE")
        _font(r, 11, bold=True, color=ROJO_BANORTE)

# ─── FastAPI ─────────────────────────────────────────────────────────────────

from fastapi import APIRouter
from fastapi.responses import Response
from pydantic import BaseModel

router = APIRouter()

class ExportarWordRequest(BaseModel):
    doc_id: str
    widgets: list[dict[str, Any]]

@router.post("/widgets/exportar-word")
async def exportar_word(body: ExportarWordRequest):
    docx_bytes = generar_word_srs(body.widgets)
    safe_id    = body.doc_id.replace("/", "_").replace(" ", "_")
    return Response(
        content=docx_bytes,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={
            "Content-Disposition": f'attachment; filename="SRS_{safe_id}.docx"',
            "Content-Length": str(len(docx_bytes)),
        },
    )


# ─── Dispatch ────────────────────────────────────────────────────────────────

RENDERERS = {
    "w_000": _render_w000,
    "w_001": _render_w001,
    "w_002": _render_w002,
    "w_003": _render_w003,
    "w_004": _render_wchart,
    "w_005": _render_w005,
}


# ─── API pública ─────────────────────────────────────────────────────────────

def generar_word_srs(widgets: list[dict]) -> bytes:
    """
    Recibe la lista de widgets exactamente como useState<Widget[]> en el frontend.
    Devuelve bytes de un .docx listo para descargar.
    """
    doc = Document()

    sec               = doc.sections[0]
    sec.page_width    = Inches(7)
    sec.page_height   = Inches(11)
    sec.left_margin   = Inches(1)
    sec.right_margin  = Inches(1)
    sec.top_margin    = Inches(1.2)
    sec.bottom_margin = Inches(1)

    doc.styles["Normal"].font.name = "Arial"
    doc.styles["Normal"].font.size = Pt(11)

    _add_header(doc)
    _add_footer(doc)
    _add_intro(doc)

    for widget in sorted(widgets, key=lambda w: w.get("posicion", 0)):
        renderer = RENDERERS.get(widget.get("id_widget", ""))
        if renderer:
            renderer(doc, widget)

    buf = io.BytesIO()
    doc.save(buf)
    buf.seek(0)
    return buf.read()