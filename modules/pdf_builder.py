"""
PDF builder — inline layout.

For each detected section of the contract:
  1. Section title header
  2. Section body text
  3. Relevant visual diagram (first time that visual type appears)

Cover page: summary + parties table + key dates.
"""

import html
import os
from pathlib import Path
from typing import Any

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import cm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    HRFlowable, Image, KeepTogether, PageBreak,
    Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle,
)

from modules.splitter import Section, split_sections

# ── Colors ─────────────────────────────────────────────────────────────────────
C_PRIMARY  = colors.HexColor("#2C3E50")
C_BLUE     = colors.HexColor("#2E86AB")
C_GREEN    = colors.HexColor("#27AE60")
C_RED      = colors.HexColor("#E74C3C")
C_ORANGE   = colors.HexColor("#F39C12")
C_PURPLE   = colors.HexColor("#8E44AD")
C_TEAL     = colors.HexColor("#1ABC9C")
C_LIGHT_BG = colors.HexColor("#F8F9FA")
C_RULE     = colors.HexColor("#DEE2E6")
C_GRAY     = colors.HexColor("#95A5A6")

PAGE_W, PAGE_H = A4

# Map visual type → accent color and label
VISUAL_META: dict[str, tuple[Any, str]] = {
    "parties":     (C_BLUE,   "Relacionamento entre as Partes"),
    "timeline":    (C_GREEN,  "Linha do Tempo"),
    "values":      (C_ORANGE, "Valores Financeiros"),
    "obligations": (C_PURPLE, "Fluxo de Obrigações"),
    "penalties":   (C_RED,    "Mapa de Penalidades"),
}


# ── Font registration ──────────────────────────────────────────────────────────

def _register_fonts() -> tuple[str, str]:
    fonts_dir = os.environ.get("IMPCON_FONTS", "")
    candidates = []
    if fonts_dir:
        d = Path(fonts_dir)
        candidates += [
            (str(d / "DejaVuSans.ttf"), str(d / "DejaVuSans-Bold.ttf")),
        ]
    candidates += [
        ("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
         "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),
        ("/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
         "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf"),
    ]
    for reg, bold in candidates:
        if os.path.exists(reg) and os.path.exists(bold):
            pdfmetrics.registerFont(TTFont("CV",      reg))
            pdfmetrics.registerFont(TTFont("CV-Bold", bold))
            return "CV", "CV-Bold"
    return "Helvetica", "Helvetica-Bold"


FONT, FONT_BOLD = _register_fonts()


# ── Styles ─────────────────────────────────────────────────────────────────────

def _styles() -> dict:
    def s(name, **kw):
        kw.pop("parent", None)
        kw.setdefault("fontName", FONT)
        return ParagraphStyle(name, **kw)

    return {
        "cover_title": s("cover_title", fontName=FONT_BOLD, fontSize=22,
                         textColor=C_PRIMARY, alignment=TA_CENTER, spaceAfter=4),
        "cover_sub":   s("cover_sub", fontSize=12, textColor=C_BLUE,
                         alignment=TA_CENTER, spaceAfter=18),
        "clause":      s("clause", fontName=FONT_BOLD, fontSize=12,
                         textColor=C_PRIMARY, spaceBefore=6, spaceAfter=4),
        "body":        s("body", fontSize=9.5, textColor=C_PRIMARY,
                         spaceAfter=5, alignment=TA_JUSTIFY, leading=14),
        "label":       s("label", fontName=FONT_BOLD, fontSize=8.5,
                         textColor=C_GRAY),
        "value":       s("value", fontName=FONT_BOLD, fontSize=9.5,
                         textColor=C_PRIMARY),
        "small":       s("small", fontSize=8, textColor=C_GRAY, leading=11),
        "diag_caption":s("diag_caption", fontSize=8, textColor=C_GRAY,
                         alignment=TA_CENTER, spaceBefore=3, spaceAfter=10),
        "section_lbl": s("section_lbl", fontName=FONT_BOLD, fontSize=7.5,
                         textColor=colors.white),
    }


def _t(v: Any) -> str:
    return html.escape(str(v or ""))


# ── Public entry point ─────────────────────────────────────────────────────────

def build_pdf(
    text: str,
    data: dict[str, Any],
    diagram_paths: dict[str, str],
    session_id: str,
    temp_dir: Path,
) -> Path:
    output = temp_dir / session_id / "contrato_visual.pdf"
    st = _styles()

    doc = SimpleDocTemplate(
        str(output),
        pagesize=A4,
        leftMargin=2.2 * cm, rightMargin=2.2 * cm,
        topMargin=2.5 * cm, bottomMargin=2.2 * cm,
        title=f"Análise — {data.get('tipo_contrato', 'Contrato')}",
    )

    story: list = []

    # ── Cover ──────────────────────────────────────────────────────────────────
    story += _cover(data, st)
    story.append(PageBreak())

    # ── Body: sections interleaved with visuals ────────────────────────────────
    sections = split_sections(text)
    used: set[str] = set()   # visual types already inserted

    for sec in sections:
        story += _section_block(sec, diagram_paths, used, st)

    # ── Append any visuals that were enabled but no matching section was found ─
    for vtype, path in diagram_paths.items():
        if vtype not in used and path and Path(path).exists():
            color, label = VISUAL_META.get(vtype, (C_BLUE, vtype.capitalize()))
            story.append(Spacer(1, 8))
            story += _visual_block(path, label, color, st)
            used.add(vtype)

    doc.build(
        story,
        onFirstPage=_page_frame,
        onLaterPages=_page_frame,
    )
    return output


# ── Cover page ─────────────────────────────────────────────────────────────────

def _cover(data: dict, st: dict) -> list:
    el = [Spacer(1, 2 * cm)]

    tipo = (data.get("tipo_contrato") or "CONTRATO").upper()
    el.append(Paragraph(_t(tipo), st["cover_title"]))
    el.append(Paragraph("Análise Visual · 100% Local · Dados Protegidos", st["cover_sub"]))
    el.append(HRFlowable(width="100%", thickness=2, color=C_BLUE, spaceAfter=16))

    # Summary
    resumo = data.get("resumo", "")
    if resumo:
        box = Table(
            [[Paragraph("Resumo Executivo", st["label"])],
             [Paragraph(_t(resumo), st["body"])]],
            colWidths=[16 * cm],
        )
        box.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (0, 0), C_BLUE),
            ("TEXTCOLOR",  (0, 0), (0, 0), colors.white),
            ("BACKGROUND", (0, 1), (0, 1), C_LIGHT_BG),
            ("PADDING",    (0, 0), (-1, -1), 10),
            ("BOX",        (0, 0), (-1, -1), 0.5, C_RULE),
        ]))
        el += [box, Spacer(1, 14)]

    # Parties table
    partes = data.get("partes", [])
    if partes:
        el.append(Paragraph("Partes Envolvidas", st["label"]))
        el.append(Spacer(1, 4))
        rows = [["Nome", "Tipo", "Papel"]]
        for p in partes:
            rows.append([
                Paragraph(_t(p.get("nome")), st["value"]),
                Paragraph(_t(p.get("tipo")), st["body"]),
                Paragraph(_t(p.get("papel")), st["small"]),
            ])
        t = Table(rows, colWidths=[6 * cm, 4 * cm, 6 * cm])
        t.setStyle(_table_style(C_PRIMARY))
        el += [t, Spacer(1, 12)]

    # Key dates
    datas = data.get("datas", [])
    if datas:
        el.append(Paragraph("Datas Principais", st["label"]))
        el.append(Spacer(1, 4))
        rows = [["Data", "Descrição", "Tipo"]]
        for d in datas:
            rows.append([
                Paragraph(_t(d.get("data") or "—"), st["value"]),
                Paragraph(_t(d.get("descricao")), st["body"]),
                Paragraph(_t(d.get("tipo")), st["small"]),
            ])
        t = Table(rows, colWidths=[3.5 * cm, 9 * cm, 3.5 * cm])
        t.setStyle(_table_style(C_GREEN))
        el += [t, Spacer(1, 8)]

    return el


# ── Section block ──────────────────────────────────────────────────────────────

def _section_block(
    sec: Section,
    diagram_paths: dict[str, str],
    used: set[str],
    st: dict,
) -> list:
    el: list = []

    # Clause header
    if sec.title:
        color, _ = VISUAL_META.get(sec.visual_type or "", (C_PRIMARY, ""))
        header_table = Table(
            [[Paragraph(_t(sec.title), st["clause"])]],
            colWidths=[16 * cm],
        )
        header_table.setStyle(TableStyle([
            ("BACKGROUND",   (0, 0), (-1, -1), color if sec.visual_type else C_PRIMARY),
            ("LEFTPADDING",  (0, 0), (-1, -1), 10),
            ("RIGHTPADDING", (0, 0), (-1, -1), 10),
            ("TOPPADDING",   (0, 0), (-1, -1), 6),
            ("BOTTOMPADDING",(0, 0), (-1, -1), 6),
            ("TEXTCOLOR",    (0, 0), (-1, -1), colors.white),
        ]))
        el.append(KeepTogether([header_table, Spacer(1, 6)]))

    # Body text — split on paragraph breaks (double newline).
    # Single newlines within a paragraph are joined as spaces.
    for block in sec.content.split("\n\n"):
        stripped = " ".join(block.split())  # collapse internal newlines/spaces
        if stripped:
            el.append(Paragraph(_t(stripped), st["body"]))

    # Visual — insert first time this type appears
    vtype = sec.visual_type
    if vtype and vtype in diagram_paths and vtype not in used:
        path = diagram_paths[vtype]
        if path and Path(path).exists():
            used.add(vtype)
            color, label = VISUAL_META[vtype]
            el.append(Spacer(1, 10))
            el += _visual_block(path, label, color, st)

    el.append(Spacer(1, 14))
    return el


# ── Visual block (diagram image with label banner) ─────────────────────────────

def _visual_block(path: str, label: str, color: Any, st: dict) -> list:
    el: list = []

    # Colored label banner
    banner = Table(
        [[Paragraph(_t(label), st["section_lbl"])]],
        colWidths=[16 * cm],
    )
    banner.setStyle(TableStyle([
        ("BACKGROUND",   (0, 0), (-1, -1), color),
        ("LEFTPADDING",  (0, 0), (-1, -1), 10),
        ("TOPPADDING",   (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING",(0, 0), (-1, -1), 5),
    ]))
    el.append(banner)

    # Image
    max_w = 15.6 * cm
    try:
        from PIL import Image as PILImage
        with PILImage.open(path) as img:
            w, h = img.size
        aspect = h / w
        iw = min(max_w, w * 0.264583)
        ih = iw * aspect
        if ih > 12 * cm:
            ih = 12 * cm
            iw = ih / aspect
        img_el = Image(path, width=iw, height=ih)
    except Exception:
        img_el = Image(path, width=max_w, height=7 * cm)

    # White background wrapper
    img_table = Table([[img_el]], colWidths=[16 * cm])
    img_table.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (-1, -1), colors.white),
        ("ALIGN",         (0, 0), (-1, -1), "CENTER"),
        ("TOPPADDING",    (0, 0), (-1, -1), 10),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
        ("BOX",           (0, 0), (-1, -1), 0.5, C_RULE),
    ]))
    el.append(img_table)

    return el


# ── Shared table style ─────────────────────────────────────────────────────────

def _table_style(header_color: Any) -> TableStyle:
    return TableStyle([
        ("BACKGROUND",    (0, 0), (-1, 0),  header_color),
        ("TEXTCOLOR",     (0, 0), (-1, 0),  colors.white),
        ("FONTNAME",      (0, 0), (-1, 0),  FONT_BOLD),
        ("FONTSIZE",      (0, 0), (-1, 0),  9),
        ("ROWBACKGROUNDS",(0, 1), (-1, -1), [colors.white, C_LIGHT_BG]),
        ("GRID",          (0, 0), (-1, -1), 0.4, C_RULE),
        ("PADDING",       (0, 0), (-1, -1), 7),
        ("VALIGN",        (0, 0), (-1, -1), "TOP"),
        ("BOX",           (0, 0), (-1, -1), 0.6, C_RULE),
    ])


# ── Page frame ─────────────────────────────────────────────────────────────────

def _page_frame(canvas, doc):
    canvas.saveState()
    top = PAGE_H - 1.6 * cm
    bot = 1.4 * cm

    canvas.setStrokeColor(C_BLUE)
    canvas.setLineWidth(0.8)
    canvas.line(2.2 * cm, top, PAGE_W - 2.2 * cm, top)
    canvas.setFont(FONT_BOLD, 7.5)
    canvas.setFillColor(C_BLUE)
    canvas.drawString(2.2 * cm, top + 3, "ImpCon")
    canvas.setFont(FONT, 7.5)
    canvas.setFillColor(C_GRAY)
    canvas.drawString(2.2 * cm + 42, top + 3, "— Análise Visual de Contratos")
    canvas.drawRightString(PAGE_W - 2.2 * cm, top + 3, "Confidencial · 100% Local")

    canvas.setStrokeColor(C_RULE)
    canvas.line(2.2 * cm, bot, PAGE_W - 2.2 * cm, bot)
    canvas.setFont(FONT, 7.5)
    canvas.setFillColor(C_GRAY)
    canvas.drawCentredString(PAGE_W / 2, bot - 0.35 * cm, f"Página {doc.page}")
    canvas.drawString(2.2 * cm, bot - 0.35 * cm,
                      "Processado localmente · Sem envio de dados externos")

    canvas.restoreState()
