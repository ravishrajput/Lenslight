"""PDF report generator using reportlab."""
import io
from datetime import datetime, timezone
from reportlab.lib.pagesizes import LETTER
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from reportlab.lib.units import inch
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
)


def _md_to_paragraphs(md: str, styles):
    """Very small markdown-ish converter → list of flowables."""
    flow = []
    for line in md.splitlines():
        s = line.strip()
        if not s:
            flow.append(Spacer(1, 6))
            continue
        if s.startswith("## "):
            flow.append(Paragraph(s[3:], styles["H2"]))
        elif s.startswith("# "):
            flow.append(Paragraph(s[2:], styles["H1"]))
        elif s.startswith("- "):
            flow.append(Paragraph("&bull;&nbsp;&nbsp;" + s[2:].replace("**", ""), styles["Body"]))
        else:
            flow.append(Paragraph(s.replace("**", ""), styles["Body"]))
    return flow


def build_report_pdf(question: str, markdown: str, artifacts: list[dict]) -> bytes:
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=LETTER, leftMargin=0.6 * inch, rightMargin=0.6 * inch, topMargin=0.6 * inch, bottomMargin=0.6 * inch)
    base = getSampleStyleSheet()
    styles = {
        "Title": ParagraphStyle("Title", parent=base["Title"], fontName="Helvetica-Bold", fontSize=20, textColor=colors.HexColor("#111111")),
        "Meta": ParagraphStyle("Meta", parent=base["Normal"], fontName="Helvetica", fontSize=9, textColor=colors.HexColor("#777777")),
        "H1": ParagraphStyle("H1", parent=base["Heading1"], fontName="Helvetica-Bold", fontSize=16, spaceAfter=8, textColor=colors.HexColor("#111111")),
        "H2": ParagraphStyle("H2", parent=base["Heading2"], fontName="Helvetica-Bold", fontSize=13, spaceBefore=10, spaceAfter=6, textColor=colors.HexColor("#111111")),
        "Body": ParagraphStyle("Body", parent=base["BodyText"], fontName="Helvetica", fontSize=10.5, leading=14, textColor=colors.HexColor("#222222")),
        "Mono": ParagraphStyle("Mono", parent=base["Code"], fontName="Courier", fontSize=8.5, textColor=colors.HexColor("#333333")),
    }

    story = []
    story.append(Paragraph("Lenslight — Data Analysis Report", styles["Title"]))
    story.append(Paragraph(datetime.now(timezone.utc).strftime("Generated %b %d, %Y %H:%M UTC"), styles["Meta"]))
    story.append(Spacer(1, 14))
    story.append(Paragraph("Question", styles["H2"]))
    story.append(Paragraph(question, styles["Body"]))
    story.append(Spacer(1, 10))
    story.append(Paragraph("Analysis", styles["H2"]))
    story.extend(_md_to_paragraphs(markdown, styles))

    # Tables
    for art in artifacts:
        if art.get("type") == "table" and art.get("rows"):
            story.append(Spacer(1, 12))
            story.append(Paragraph(art.get("title", "Table"), styles["H2"]))
            rows = art["rows"]
            headers = list(rows[0].keys())
            data = [headers] + [[str(r.get(h, "")) for h in headers] for r in rows]
            t = Table(data, hAlign="LEFT")
            t.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#111111")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTNAME", (0, 1), (-1, -1), "Courier"),
                ("FONTSIZE", (0, 0), (-1, -1), 9),
                ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#CCCCCC")),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F6F6F6")]),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]))
            story.append(t)
        elif art.get("type") == "query":
            story.append(Spacer(1, 10))
            story.append(Paragraph(art.get("title", "Query"), styles["H2"]))
            story.append(Paragraph(art.get("code", "").replace("<", "&lt;").replace(">", "&gt;"), styles["Mono"]))

    doc.build(story)
    return buf.getvalue()
