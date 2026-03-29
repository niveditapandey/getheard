"""
PDF Report Generator — converts a GetHeard research report dict into a clean,
branded A4 PDF using ReportLab Platypus.

Pages:
  1.  Cover
  2.  Executive Summary
  3.  At-a-Glance (sentiment + key stat)
  4+. Respondent Personas
  5+. Key Themes
  6+. Pain Points & Positive Highlights
  7+. Recommendations
  8+. Notable Quotes
  9+. Research Gaps & Next Steps
"""

import io
import logging
from datetime import datetime
from typing import Optional

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import (
    BaseDocTemplate,
    Frame,
    HRFlowable,
    NextPageTemplate,
    PageBreak,
    PageTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
)

logger = logging.getLogger(__name__)

PAGE_W, PAGE_H = A4
MARGIN = 1.8 * cm

LANG_NAMES = {
    "en": "English", "hi": "Hindi", "id": "Indonesian", "fil": "Filipino",
    "th": "Thai", "vi": "Vietnamese", "ko": "Korean", "ja": "Japanese", "zh": "Mandarin",
}


# ── Colour helpers ──────────────────────────────────────────────────────────────

def _hex(h: str):
    """Convert '#rrggbb' to ReportLab HexColor."""
    h = h.lstrip("#")
    return colors.HexColor(f"#{h}")


def _brand_color(branding: dict):
    raw = branding.get("brand_color", "#1e3c72") if branding else "#1e3c72"
    try:
        return _hex(raw)
    except Exception:
        return _hex("#1e3c72")


NAVY   = _hex("#1e3c72")
NAVY_D = _hex("#0f2244")
GRAY   = _hex("#6b7280")
LGRAY  = _hex("#f0f4f8")
GREEN  = _hex("#22c55e")
AMBER  = _hex("#f59e0b")
RED    = _hex("#ef4444")
DARK   = _hex("#1f2937")
WHITE  = colors.white

SENT_COLORS = {"positive": GREEN, "neutral": AMBER, "negative": RED, "mixed": AMBER}
PRI_COLORS  = {"high": RED,   "medium": AMBER, "low": GREEN}
SEV_COLORS  = {"high": RED,   "medium": AMBER, "low": GREEN}


# ── Styles ──────────────────────────────────────────────────────────────────────

def _make_styles(accent):
    base = getSampleStyleSheet()
    return {
        "h1": ParagraphStyle("h1", fontName="Helvetica-Bold", fontSize=22, textColor=WHITE,
                             leading=28, spaceAfter=6),
        "h2": ParagraphStyle("h2", fontName="Helvetica-Bold", fontSize=14, textColor=accent,
                             leading=18, spaceBefore=14, spaceAfter=6),
        "h3": ParagraphStyle("h3", fontName="Helvetica-Bold", fontSize=11, textColor=DARK,
                             leading=14, spaceBefore=8, spaceAfter=4),
        "body": ParagraphStyle("body", fontName="Helvetica", fontSize=10, textColor=DARK,
                               leading=14, spaceAfter=6),
        "small": ParagraphStyle("small", fontName="Helvetica", fontSize=8, textColor=GRAY,
                                leading=11, spaceAfter=4),
        "italic": ParagraphStyle("italic", fontName="Helvetica-Oblique", fontSize=10,
                                 textColor=GRAY, leading=14, spaceAfter=6),
        "quote": ParagraphStyle("quote", fontName="Helvetica-Oblique", fontSize=10,
                                textColor=DARK, leading=14, spaceAfter=4,
                                leftIndent=12, borderPad=4),
        "label": ParagraphStyle("label", fontName="Helvetica-Bold", fontSize=8,
                                textColor=WHITE, leading=10),
        "center": ParagraphStyle("center", fontName="Helvetica", fontSize=10, textColor=DARK,
                                 leading=14, alignment=TA_CENTER),
        "cover_title": ParagraphStyle("cover_title", fontName="Helvetica-Bold", fontSize=28,
                                      textColor=WHITE, leading=34, spaceAfter=10),
        "cover_sub": ParagraphStyle("cover_sub", fontName="Helvetica", fontSize=12,
                                    textColor=_hex("#b0c4de"), leading=16, spaceAfter=6),
        "cover_meta": ParagraphStyle("cover_meta", fontName="Helvetica", fontSize=9,
                                     textColor=_hex("#7da0d0"), leading=13),
    }


# ── Page templates ─────────────────────────────────────────────────────────────

def _cover_page(canvas, doc, branding):
    accent = _brand_color(branding)
    canvas.saveState()
    # Full-bleed navy background
    canvas.setFillColor(NAVY_D)
    canvas.rect(0, 0, PAGE_W, PAGE_H, fill=1, stroke=0)
    # Accent stripe
    canvas.setFillColor(accent)
    canvas.rect(0, PAGE_H * 0.38, PAGE_W, 3, fill=1, stroke=0)
    # Left accent bar
    canvas.rect(0, 0, 4, PAGE_H, fill=1, stroke=0)
    canvas.restoreState()


def _content_page(canvas, doc, branding, report):
    accent = _brand_color(branding)
    canvas.saveState()
    # Top accent bar
    canvas.setFillColor(accent)
    canvas.rect(0, PAGE_H - 8, PAGE_W, 8, fill=1, stroke=0)
    # Footer line
    canvas.setFillColor(LGRAY)
    canvas.rect(MARGIN, 1.0 * cm, PAGE_W - 2 * MARGIN, 1, fill=1, stroke=0)
    # Footer text
    brand_name = branding.get("brand_name", "") if branding else ""
    project_name = report.get("project_name", "GetHeard Research Report")
    left_text = f"{project_name}"
    if brand_name:
        left_text = f"{brand_name}  ·  {project_name}"
    canvas.setFont("Helvetica", 7)
    canvas.setFillColor(GRAY)
    canvas.drawString(MARGIN, 0.7 * cm, left_text)
    canvas.drawRightString(PAGE_W - MARGIN, 0.7 * cm, f"Confidential  ·  Page {doc.page}")
    canvas.restoreState()


# ── Section builders ────────────────────────────────────────────────────────────

def _section_header(title: str, styles: dict, accent) -> list:
    return [
        HRFlowable(width="100%", thickness=2, color=accent, spaceAfter=6),
        Paragraph(title, styles["h2"]),
    ]


def _pill_table(text: str, fill_color, text_color=WHITE) -> Table:
    t = Table([[Paragraph(f"<b>{text.upper()}</b>",
                ParagraphStyle("pill", fontName="Helvetica-Bold", fontSize=7,
                               textColor=text_color, leading=9))]],
              colWidths=[max(1.5 * cm, len(text) * 0.2 * cm + 0.6 * cm)])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), fill_color),
        ("ROWBACKGROUNDS", (0, 0), (-1, -1), [fill_color]),
        ("TOPPADDING", (0, 0), (-1, -1), 2),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("ROUNDEDCORNERS", [4, 4, 4, 4]),
    ]))
    return t


def _stat_row(stats: list, accent) -> Table:
    """4-column stat boxes."""
    col_w = (PAGE_W - 2 * MARGIN) / len(stats)
    header_style = ParagraphStyle("sv", fontName="Helvetica-Bold", fontSize=20,
                                   textColor=accent, leading=24, alignment=TA_CENTER)
    label_style  = ParagraphStyle("sl", fontName="Helvetica", fontSize=8,
                                   textColor=GRAY, leading=11, alignment=TA_CENTER)
    cells = [[Paragraph(str(v), header_style) for v, _ in stats],
             [Paragraph(l, label_style) for _, l in stats]]
    t = Table(cells, colWidths=[col_w] * len(stats))
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), LGRAY),
        ("BOX", (0, 0), (-1, -1), 0.5, _hex("#e2e8f0")),
        ("GRID", (0, 0), (-1, -1), 0.5, WHITE),
        ("TOPPADDING", (0, 0), (-1, 0), 10),
        ("BOTTOMPADDING", (0, 0), (-1, 0), 4),
        ("TOPPADDING", (0, 1), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 1), (-1, -1), 10),
    ]))
    return t


def _build_cover(report: dict, branding: dict, styles: dict) -> list:
    brand_name = branding.get("brand_name", "") if branding else ""
    meta_parts = [
        f"Respondents: {report.get('total_transcripts', 0)}",
        f"Type: {(report.get('research_type', 'CX')).upper()}",
        f"Languages: {', '.join(LANG_NAMES.get(l, l) for l in report.get('languages', []))}",
        f"Generated: {datetime.fromisoformat(report.get('generated_at', datetime.now().isoformat())).strftime('%d %b %Y')}",
    ]
    elems = [
        Spacer(1, PAGE_H * 0.12),
        Paragraph(report.get("project_name", "Research Report"), styles["cover_title"]),
    ]
    if report.get("objective"):
        elems.append(Paragraph(report["objective"][:200], styles["cover_sub"]))
    elems.append(Spacer(1, 0.5 * cm))
    elems.append(Paragraph("  ·  ".join(meta_parts), styles["cover_meta"]))
    if brand_name:
        elems.append(Spacer(1, 0.8 * cm))
        elems.append(Paragraph(f"Prepared for {brand_name}",
                               ParagraphStyle("pf", fontName="Helvetica-Oblique", fontSize=10,
                                              textColor=_hex("#7da0d0"), leading=14)))
    elems.append(Paragraph("Confidential — Prepared by GetHeard · getheard.space",
                            ParagraphStyle("conf", fontName="Helvetica-Oblique", fontSize=8,
                                           textColor=_hex("#4a6a9a"), leading=12)))
    return elems


def _build_exec_summary(report: dict, styles: dict, accent) -> list:
    elems = _section_header("Executive Summary", styles, accent)
    summary = report.get("executive_summary", "No summary available.")
    for para in summary.split("\n"):
        if para.strip():
            elems.append(Paragraph(para.strip(), styles["body"]))
    if report.get("key_stat"):
        elems.append(Spacer(1, 0.3 * cm))
        t = Table([[Paragraph(f"💡  {report['key_stat']}",
                    ParagraphStyle("ks", fontName="Helvetica-Bold", fontSize=11,
                                   textColor=accent, leading=14))]],
                  colWidths=[PAGE_W - 2 * MARGIN])
        t.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), LGRAY),
            ("TOPPADDING", (0, 0), (-1, -1), 10),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
            ("LEFTPADDING", (0, 0), (-1, -1), 14),
        ]))
        elems.append(t)
    if report.get("confidence_notes"):
        elems.append(Spacer(1, 0.3 * cm))
        elems.append(Paragraph(f"ℹ  {report['confidence_notes']}", styles["italic"]))
    return elems


def _build_at_a_glance(report: dict, styles: dict, accent) -> list:
    elems = _section_header("At a Glance", styles, accent)
    themes = report.get("key_themes", [])
    recs   = report.get("recommendations", [])
    sent   = report.get("sentiment_overview", {})
    stats  = [
        (report.get("total_transcripts", 0), "Respondents"),
        (len(themes), "Key Themes"),
        (len([r for r in recs if r.get("priority") == "high"]), "High-Priority Actions"),
        ((sent.get("overall") or "—").capitalize(), "Overall Sentiment"),
    ]
    elems.append(_stat_row(stats, accent))
    elems.append(Spacer(1, 0.4 * cm))

    # Sentiment bar as table row
    pos = sent.get("positive_pct", 0) or 0
    neu = sent.get("neutral_pct", 0) or 0
    neg = sent.get("negative_pct", 0) or 0
    bar_w = PAGE_W - 2 * MARGIN
    sent_data = [[""]]  # placeholder — drawn via table background trick
    if pos + neu + neg > 0:
        # Build proportional color columns
        cols_data = [[""]*3]
        col_ws = [bar_w * pos / 100, bar_w * neu / 100, bar_w * neg / 100]
        col_ws = [max(w, 0.01 * cm) for w in col_ws]  # avoid zero
        sbar = Table(cols_data, colWidths=col_ws, rowHeights=[0.5 * cm])
        sbar.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (0, 0), GREEN),
            ("BACKGROUND", (1, 0), (1, 0), AMBER),
            ("BACKGROUND", (2, 0), (2, 0), RED),
        ]))
        elems.append(sbar)
        legend = f"  ■ Positive {pos}%    ■ Neutral {neu}%    ■ Negative {neg}%"
        elems.append(Paragraph(legend, styles["small"]))
        if sent.get("sentiment_narrative"):
            elems.append(Paragraph(sent["sentiment_narrative"], styles["italic"]))
    return elems


def _build_personas(report: dict, styles: dict, accent) -> list:
    personas = report.get("personas", [])
    if not personas:
        return []
    elems = _section_header("Respondent Personas", styles, accent)
    elems.append(Paragraph("Behavioral archetypes derived from the interview data", styles["small"]))
    elems.append(Spacer(1, 0.2 * cm))

    for p in personas[:4]:
        pct = p.get("percentage", "?")
        traits = ", ".join(p.get("characteristics", [])[:3])
        row_data = [
            [Paragraph(f"<b>{p.get('name','Persona')}</b>  ({pct}%)",
                       ParagraphStyle("pn", fontName="Helvetica-Bold", fontSize=11,
                                      textColor=accent, leading=14)),
             Paragraph(p.get("description", "")[:300], styles["body"])],
            [Paragraph(f"Traits: {traits}", styles["small"]) if traits else Paragraph("", styles["small"]),
             Paragraph(f"Needs: {p.get('what_they_need','')[:200]}", styles["small"])],
        ]
        if p.get("key_quote"):
            row_data.append([
                Paragraph("", styles["small"]),
                Paragraph(f'"{p["key_quote"][:220]}"', styles["quote"]),
            ])
        cw = (PAGE_W - 2 * MARGIN)
        t = Table(row_data, colWidths=[3 * cm, cw - 3 * cm])
        t.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), LGRAY),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("TOPPADDING", (0, 0), (-1, -1), 8),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ("LEFTPADDING", (0, 0), (-1, -1), 10),
            ("RIGHTPADDING", (0, 0), (-1, -1), 10),
            ("BOX", (0, 0), (-1, -1), 0.5, _hex("#e2e8f0")),
            ("LINEBELOW", (0, 0), (-1, 0), 0.5, _hex("#e2e8f0")),
        ]))
        elems.append(t)
        elems.append(Spacer(1, 0.3 * cm))
    return elems


def _build_themes(report: dict, styles: dict, accent) -> list:
    themes = report.get("key_themes", [])
    if not themes:
        return []
    elems = _section_header("Key Themes", styles, accent)
    max_freq = max((t.get("frequency", 1) for t in themes), default=1)
    col_w = PAGE_W - 2 * MARGIN
    bar_max = col_w * 0.45

    for t in themes[:10]:
        freq = t.get("frequency", 0)
        pct  = t.get("frequency_pct", 0)
        sent = t.get("sentiment", "neutral")
        scolor = SENT_COLORS.get(sent, AMBER)
        bar_w  = max(0.2 * cm, bar_max * freq / max_freq)

        name_cell = [
            Paragraph(f"<b>{t.get('theme','')}</b>", styles["h3"]),
            Paragraph(t.get("description", "")[:200], styles["small"]),
        ]
        bar_cell = [
            _pill_table(sent, scolor),
            Spacer(1, 0.1 * cm),
            Table([[""]], colWidths=[bar_w], rowHeights=[0.35 * cm],
                  style=TableStyle([("BACKGROUND", (0, 0), (-1, -1), scolor)])),
            Paragraph(f"{freq} ({pct}%)", styles["small"]),
        ]
        row = Table([[name_cell, bar_cell]], colWidths=[col_w * 0.6, col_w * 0.4])
        row.setStyle(TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("TOPPADDING", (0, 0), (-1, -1), 6),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ("LEFTPADDING", (0, 0), (-1, -1), 0),
            ("RIGHTPADDING", (0, 0), (-1, -1), 0),
            ("LINEBELOW", (0, 0), (-1, -1), 0.5, _hex("#e2e8f0")),
        ]))
        elems.append(row)
    return elems


def _build_pains_positives(report: dict, styles: dict, accent) -> list:
    pains     = report.get("pain_points", [])
    positives = report.get("positive_highlights", [])
    elems = []
    col_w = (PAGE_W - 2 * MARGIN)

    if pains:
        elems += _section_header("Pain Points", styles, accent)
        for p in pains[:8]:
            sev = p.get("severity", "medium")
            scolor = SEV_COLORS.get(sev, AMBER)
            content = [
                [_pill_table(sev, scolor),
                 Paragraph(f"<b>{p.get('pain_point','')}</b>", styles["h3"])],
            ]
            if p.get("business_impact"):
                content.append([Spacer(1, 0), Paragraph(f"💼 {p['business_impact'][:150]}", styles["small"])])
            if p.get("example"):
                content.append([Spacer(1, 0), Paragraph(f'"{p["example"][:150]}"', styles["quote"])])
            t = Table(content, colWidths=[2.2 * cm, col_w - 2.2 * cm])
            t.setStyle(TableStyle([
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                ("BACKGROUND", (0, 0), (-1, -1), _hex("#fff5f5")),
                ("BOX", (0, 0), (-1, -1), 0.5, _hex("#fecaca")),
                ("LINEBELOW", (0, 0), (-1, 0), 0.5, _hex("#fecaca")),
            ]))
            elems.append(t)
            elems.append(Spacer(1, 0.2 * cm))

    if positives:
        elems += _section_header("Positive Highlights", styles, accent)
        for p in positives[:6]:
            t = Table(
                [[Paragraph(f"<b>{p.get('highlight','')}</b>", styles["h3"])],
                 [Paragraph(p.get("business_value", "")[:200], styles["small"])]],
                colWidths=[col_w])
            t.setStyle(TableStyle([
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                ("LEFTPADDING", (0, 0), (-1, -1), 12),
                ("BACKGROUND", (0, 0), (-1, -1), _hex("#f0fdf4")),
                ("BOX", (0, 0), (-1, -1), 0.5, _hex("#bbf7d0")),
                ("LINEBEFORE", (0, 0), (0, -1), 3, GREEN),
            ]))
            elems.append(t)
            elems.append(Spacer(1, 0.2 * cm))
    return elems


def _build_recommendations(report: dict, styles: dict, accent) -> list:
    recs = report.get("recommendations", [])
    if not recs:
        return []
    order = {"high": 0, "medium": 1, "low": 2}
    recs = sorted(recs, key=lambda r: order.get(r.get("priority", "medium"), 1))
    elems = _section_header("Recommendations", styles, accent)
    col_w = PAGE_W - 2 * MARGIN
    pri_bg = {"high": _hex("#fff5f5"), "medium": _hex("#fffbf5"), "low": _hex("#f0fdf4")}
    pri_border = {"high": _hex("#fecaca"), "medium": _hex("#fed7aa"), "low": _hex("#bbf7d0")}

    for rec in recs[:8]:
        pri = rec.get("priority", "medium")
        pcolor = PRI_COLORS.get(pri, AMBER)
        bg = pri_bg.get(pri, LGRAY)
        border = pri_border.get(pri, _hex("#e2e8f0"))
        content = [
            [_pill_table(pri, pcolor),
             Paragraph(f"<b>{rec.get('recommendation','')}</b>", styles["h3"])],
        ]
        if rec.get("rationale"):
            content.append([Spacer(1, 0), Paragraph(rec["rationale"][:200], styles["small"])])
        if rec.get("expected_impact"):
            content.append([Spacer(1, 0),
                            Paragraph(f"→ {rec['expected_impact'][:150]}", styles["small"])])
        owner = rec.get("who_owns_it", "")
        if owner:
            content.append([Spacer(1, 0), Paragraph(f"Owner: {owner}", styles["small"])])
        t = Table(content, colWidths=[2.2 * cm, col_w - 2.2 * cm])
        t.setStyle(TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("TOPPADDING", (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ("LEFTPADDING", (0, 0), (-1, -1), 6),
            ("RIGHTPADDING", (0, 0), (-1, -1), 6),
            ("BACKGROUND", (0, 0), (-1, -1), bg),
            ("BOX", (0, 0), (-1, -1), 0.5, border),
        ]))
        elems.append(t)
        elems.append(Spacer(1, 0.2 * cm))
    return elems


def _build_quotes(report: dict, styles: dict, accent) -> list:
    quotes = report.get("notable_quotes", [])
    if not quotes:
        return []
    elems = _section_header("Notable Quotes", styles, accent)
    col_w = PAGE_W - 2 * MARGIN
    sent_color = {"positive": GREEN, "negative": RED, "neutral": NAVY}

    for q in quotes[:8]:
        sc = sent_color.get(q.get("sentiment", "neutral"), NAVY)
        lang = LANG_NAMES.get(q.get("language", "en"), q.get("language", ""))
        ctx  = q.get("context", "")
        meta = f"{lang}  ·  {ctx}"[:100] if ctx else lang
        t = Table(
            [[Paragraph(f'"{q.get("quote", "")[:280]}"', styles["quote"])],
             [Paragraph(meta, styles["small"])]],
            colWidths=[col_w])
        t.setStyle(TableStyle([
            ("TOPPADDING", (0, 0), (-1, -1), 8),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ("LEFTPADDING", (0, 0), (-1, -1), 16),
            ("BACKGROUND", (0, 0), (-1, -1), _hex("#f9fafb")),
            ("BOX", (0, 0), (-1, -1), 0.5, _hex("#e5e7eb")),
            ("LINEBEFORE", (0, 0), (0, -1), 3, sc),
        ]))
        elems.append(t)
        elems.append(Spacer(1, 0.25 * cm))
    return elems


def _build_gaps(report: dict, styles: dict, accent) -> list:
    gaps = report.get("research_gaps", [])
    if not gaps:
        return []
    elems = _section_header("Research Gaps & Next Steps", styles, accent)
    col_w = PAGE_W - 2 * MARGIN
    for g in gaps[:8]:
        t = Table([[Paragraph(f"• {g}", styles["body"])]], colWidths=[col_w])
        t.setStyle(TableStyle([
            ("TOPPADDING", (0, 0), (-1, -1), 6),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ("LEFTPADDING", (0, 0), (-1, -1), 12),
            ("BACKGROUND", (0, 0), (-1, -1), _hex("#fff7ed")),
            ("BOX", (0, 0), (-1, -1), 0.5, _hex("#fed7aa")),
        ]))
        elems.append(t)
        elems.append(Spacer(1, 0.15 * cm))
    return elems


# ── Public API ──────────────────────────────────────────────────────────────────

def generate_pdf(report: dict, branding: Optional[dict] = None) -> bytes:
    """
    Convert a report dict into a branded A4 PDF and return as bytes.
    """
    buf = io.BytesIO()
    accent = _brand_color(branding)
    styles = _make_styles(accent)

    # Frame definitions
    cover_frame   = Frame(MARGIN, MARGIN, PAGE_W - 2 * MARGIN, PAGE_H - 2 * MARGIN, id="cover")
    content_frame = Frame(MARGIN, 1.8 * cm, PAGE_W - 2 * MARGIN, PAGE_H - 3.2 * cm, id="content")

    def _on_cover(canvas, doc):
        _cover_page(canvas, doc, branding or {})

    def _on_content(canvas, doc):
        _content_page(canvas, doc, branding or {}, report)

    cover_tpl   = PageTemplate(id="cover",   frames=[cover_frame],   onPage=_on_cover)
    content_tpl = PageTemplate(id="content", frames=[content_frame], onPage=_on_content)

    doc = BaseDocTemplate(
        buf,
        pagesize=A4,
        pageTemplates=[cover_tpl, content_tpl],
        leftMargin=MARGIN, rightMargin=MARGIN,
        topMargin=MARGIN,  bottomMargin=MARGIN,
    )

    story = []

    # ── Cover page ──
    story += _build_cover(report, branding or {}, styles)
    story.append(NextPageTemplate("content"))
    story.append(PageBreak())

    # ── Executive Summary ──
    story += _build_exec_summary(report, styles, accent)
    story.append(Spacer(1, 0.5 * cm))
    story += _build_at_a_glance(report, styles, accent)
    story.append(PageBreak())

    # ── Personas ──
    personas_elems = _build_personas(report, styles, accent)
    if personas_elems:
        story += personas_elems
        story.append(PageBreak())

    # ── Themes ──
    themes_elems = _build_themes(report, styles, accent)
    if themes_elems:
        story += themes_elems
        story.append(PageBreak())

    # ── Pains + Positives ──
    pp_elems = _build_pains_positives(report, styles, accent)
    if pp_elems:
        story += pp_elems
        story.append(PageBreak())

    # ── Recommendations ──
    rec_elems = _build_recommendations(report, styles, accent)
    if rec_elems:
        story += rec_elems
        story.append(PageBreak())

    # ── Quotes ──
    quote_elems = _build_quotes(report, styles, accent)
    if quote_elems:
        story += quote_elems
        story.append(PageBreak())

    # ── Gaps ──
    gap_elems = _build_gaps(report, styles, accent)
    if gap_elems:
        story += gap_elems

    doc.build(story)
    buf.seek(0)
    logger.info(f"Generated PDF for report {report.get('report_id')}")
    return buf.read()
