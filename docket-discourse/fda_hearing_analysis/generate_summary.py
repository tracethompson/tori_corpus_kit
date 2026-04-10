#!/usr/bin/env python3
"""Generate a stakeholder-ready PDF summary of FDA hearing comment analysis."""

import math
import os
import sqlite3
import statistics

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    HRFlowable, KeepTogether,
)

DB_PATH = os.path.join(os.path.dirname(__file__), "fda_hearings.db")
PDF_PATH = os.path.join(os.path.dirname(__file__), "fda_hearing_summary.pdf")

BLUE = colors.HexColor("#1e40af")
DARK = colors.HexColor("#1e293b")
BODY_COLOR = colors.HexColor("#334155")
MUTED = colors.HexColor("#64748b")
LIGHT_BG = colors.HexColor("#f8fafc")
BORDER = colors.HexColor("#e2e8f0")
RED = colors.HexColor("#dc2626")


def pct(sorted_data, p):
    n = len(sorted_data)
    if n == 0:
        return 0
    k = (p / 100) * (n - 1)
    f, c = math.floor(k), math.ceil(k)
    if f == c:
        return sorted_data[int(k)]
    return sorted_data[f] * (c - k) + sorted_data[c] * (k - f)


def pct_rank(sorted_data, value):
    n = len(sorted_data)
    return (sum(1 for v in sorted_data if v <= value) / n) * 100 if n else 0


def build_pdf():
    conn = sqlite3.connect(DB_PATH)

    all_rows = conn.execute(
        "SELECT docket_id, docket_title, total_comments, hearing_notice_title, flagged_fp "
        "FROM dockets ORDER BY total_comments DESC"
    ).fetchall()
    counts_all = sorted([r[2] for r in all_rows])

    clean_rows = [r for r in all_rows if r[4] == 0]
    counts_clean = sorted([r[2] for r in clean_rows])

    fp_rows = [r for r in all_rows if r[4] == 1]
    counts_fp = sorted([r[2] for r in fp_rows])

    top10 = all_rows[:10]
    top10_clean = sorted(clean_rows, key=lambda r: r[2], reverse=True)[:10]

    conn.close()

    # ── Styles ───────────────────────────────────────────────────────────
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle("DocTitle", parent=styles["Title"], fontSize=18,
                              spaceAfter=2, textColor=DARK, fontName="Helvetica-Bold"))
    styles.add(ParagraphStyle("Sub", parent=styles["Normal"], fontSize=10,
                              textColor=MUTED, spaceAfter=14))
    styles.add(ParagraphStyle("SH", parent=styles["Heading2"], fontSize=13,
                              spaceBefore=18, spaceAfter=8, textColor=BLUE))
    styles.add(ParagraphStyle("Body", parent=styles["Normal"], fontSize=9.5,
                              leading=13.5, spaceAfter=6, textColor=BODY_COLOR))
    styles.add(ParagraphStyle("Callout", parent=styles["Normal"], fontSize=10,
                              leading=14, textColor=RED, spaceBefore=4, spaceAfter=8,
                              fontName="Helvetica-Bold"))
    styles.add(ParagraphStyle("Note", parent=styles["Normal"], fontSize=8,
                              leading=10, textColor=MUTED, spaceAfter=4))

    doc = SimpleDocTemplate(PDF_PATH, pagesize=letter,
                            leftMargin=0.8 * inch, rightMargin=0.8 * inch,
                            topMargin=0.65 * inch, bottomMargin=0.6 * inch)
    story = []

    # ── Header ───────────────────────────────────────────────────────────
    story.append(Spacer(1, 0.3 * inch))
    story.append(Paragraph("FDA Public-Hearing Dockets: Comment Volume Analysis", styles["DocTitle"]))
    story.append(Paragraph("2008\u2013Present &nbsp;|&nbsp; Data from regulations.gov API v4 &nbsp;|&nbsp; February 2026", styles["Sub"]))
    story.append(HRFlowable(width="100%", thickness=1, color=BORDER))
    story.append(Spacer(1, 8))

    # ── Overview ─────────────────────────────────────────────────────────
    story.append(Paragraph("Overview", styles["SH"]))
    story.append(Paragraph(
        f"We queried the regulations.gov API for all FDA Notice-type documents mentioning "
        f"\u201cpublic hearing\u201d (and the variant \u201cpublic hearing request for comments\u201d) "
        f"posted on or after January 1, 2008. After deduplication, this produced "
        f"<b>{len(all_rows)} unique dockets</b>.",
        styles["Body"],
    ))
    story.append(Paragraph(
        f"For each docket, we counted total public comments by querying the <i>/v4/comments</i> "
        f"endpoint for every document with an active comment period. Comment counts were summed "
        f"across all documents within each docket.",
        styles["Body"],
    ))

    # ── False-positive explanation ────────────────────────────────────────
    story.append(Paragraph("Important Note: Search Precision and False Positives", styles["SH"]))
    story.append(Paragraph(
        f"The regulations.gov API\u2019s <font face='Courier' size=8>searchTerm</font> parameter "
        f"performs <b>full-text search</b> across the entire document body\u2014not a title-only "
        f"filter. This means any FDA Notice that mentions the phrase \u201cpublic hearing\u201d "
        f"anywhere in its text is returned, even if the document itself is not a hearing notice.",
        styles["Body"],
    ))
    story.append(Paragraph(
        f"To identify likely false positives, we checked whether each docket\u2019s notice title "
        f"contained hearing-related keywords: \u201cpublic hearing,\u201d \u201chearing; request "
        f"for comments,\u201d \u201cnotice of hearing,\u201d or \u201cpublic meeting.\u201d",
        styles["Body"],
    ))
    story.append(Paragraph(
        f"<b>Result: {len(fp_rows)} of {len(all_rows)} dockets ({len(fp_rows)/len(all_rows)*100:.0f}%) "
        f"were flagged as probable false positives.</b> "
        f"The remaining <b>{len(clean_rows)} dockets</b> have titles that explicitly reference "
        f"a public hearing or public meeting.",
        styles["Callout"],
    ))
    story.append(Paragraph(
        "Common false-positive categories include: advisory committee meeting notices "
        "(which reference hearing procedures in boilerplate text), patent extension determinations, "
        "debarment orders, and \u201cEstablishment of a Public Docket; Request for Comments\u201d "
        "notices that solicit written comments but do not involve an actual hearing.",
        styles["Body"],
    ))
    story.append(Paragraph(
        "We present statistics both ways\u2014all 584 dockets and the 61 confirmed hearing dockets"
        "\u2014so the reader can assess impact with or without the false positives.",
        styles["Body"],
    ))

    # ── Summary statistics ───────────────────────────────────────────────
    story.append(Paragraph("Summary Statistics", styles["SH"]))

    def f(v):
        return f"{v:,.1f}" if isinstance(v, float) else f"{v:,}"

    stats = [
        ["Metric", f"All Dockets (n={len(all_rows)})", f"Confirmed Hearings (n={len(clean_rows)})"],
        ["Mean", f(statistics.mean(counts_all)), f(statistics.mean(counts_clean))],
        ["Median", f(statistics.median(counts_all)), f(statistics.median(counts_clean))],
        ["75th percentile", f(pct(counts_all, 75)), f(pct(counts_clean, 75))],
        ["90th percentile", f(pct(counts_all, 90)), f(pct(counts_clean, 90))],
        ["95th percentile", f(pct(counts_all, 95)), f(pct(counts_clean, 95))],
        ["99th percentile", f(pct(counts_all, 99)), f(pct(counts_clean, 99))],
        ["6,950 comments \u2192 percentile rank",
         f"{pct_rank(counts_all, 6950):.1f}%",
         f"{pct_rank(counts_clean, 6950):.1f}%"],
    ]
    t = Table(stats, colWidths=[1.8 * inch, 2.2 * inch, 2.2 * inch])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), BLUE),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
        ("ALIGN", (0, 0), (0, -1), "LEFT"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [LIGHT_BG, colors.white]),
        ("GRID", (0, 0), (-1, -1), 0.5, BORDER),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
    ]))
    story.append(t)
    story.append(Spacer(1, 6))

    story.append(Paragraph(
        "6,950 comments (docket FDA-2015-D-3719) falls at the <b>99th percentile</b> across all "
        "584 dockets and at the <b>100th percentile</b> among the 61 confirmed hearing dockets "
        "\u2014 meaning it would be the single highest comment count in the confirmed set.",
        styles["Callout"],
    ))

    # ── Top 10: All dockets ──────────────────────────────────────────────
    story.append(Paragraph("Top 10 Dockets by Comment Count (All Dockets)", styles["SH"]))

    def make_top_table(rows):
        data = [["Rank", "Docket ID", "Title", "Comments"]]
        for i, row in enumerate(rows, 1):
            title = (row[1] or "")[:58]
            if len(row[1] or "") > 58:
                title += "\u2026"
            data.append([str(i), row[0], title, f"{row[2]:,}"])
        t = Table(data, colWidths=[0.4 * inch, 1.55 * inch, 3.3 * inch, 0.95 * inch])
        t.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), BLUE),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 8),
            ("ALIGN", (0, 0), (0, -1), "CENTER"),
            ("ALIGN", (3, 0), (3, -1), "RIGHT"),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [LIGHT_BG, colors.white]),
            ("GRID", (0, 0), (-1, -1), 0.5, BORDER),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ("LEFTPADDING", (0, 0), (-1, -1), 5),
            ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ]))
        return t

    story.append(make_top_table(top10))
    story.append(Spacer(1, 6))
    story.append(Paragraph(
        "Five of the top 10 are Vaccines and Related Biological Products Advisory Committee "
        "(VRBPAC) meetings, reflecting intense public engagement with FDA vaccine decisions "
        "during and after the COVID-19 pandemic. These dockets dominate the right tail of the "
        "distribution and significantly inflate the mean (549) relative to the median (2.5).",
        styles["Body"],
    ))

    # ── Top 10: Confirmed hearings only ──────────────────────────────────
    story.append(Paragraph("Top 10 Dockets by Comment Count (Confirmed Hearings Only)", styles["SH"]))
    story.append(make_top_table(top10_clean))
    story.append(Spacer(1, 10))

    # ── Context for FDA-2015-D-3719 ──────────────────────────────────────
    story.append(Paragraph("Context: Docket FDA-2015-D-3719", styles["SH"]))
    story.append(Paragraph(
        "Docket FDA-2015-D-3719 (\u201cDraft Guidances Relating to the Regulation of Human Cells, "
        "Tissues, and Cellular and Tissue-Based Products\u201d) received approximately <b>6,950 "
        "public comments</b>. This docket is a Draft Guidance, not a Notice, and therefore did "
        "not appear in our search results. However, its comment count serves as a useful benchmark.",
        styles["Body"],
    ))
    story.append(Paragraph(
        "Against the full set of 584 public-hearing-related dockets, 6,950 comments places at the "
        "<b>99th percentile</b>\u2014only 6 of 584 dockets received more. Against the 61 confirmed "
        "hearing dockets, it would rank <b>1st</b>, exceeding the next-highest by a wide margin.",
        styles["Body"],
    ))
    story.append(Paragraph(
        "This level of engagement is exceptional by any measure. The only dockets surpassing it are "
        "driven by organized mass-comment campaigns (primarily related to COVID-19 vaccines), "
        "a dynamic qualitatively different from typical regulatory comment activity.",
        styles["Body"],
    ))

    # ── Methodology ──────────────────────────────────────────────────────
    story.append(Paragraph("Methodology", styles["SH"]))
    story.append(Paragraph(
        "<b>Data source:</b> regulations.gov API v4 (api.regulations.gov), queried February 2026.",
        styles["Body"],
    ))
    story.append(Paragraph(
        "<b>Docket discovery:</b> Searched <i>/v4/documents</i> for FDA Notices with "
        "<font face='Courier' size=8>searchTerm=public+hearing</font> and "
        "<font face='Courier' size=8>searchTerm=public+hearing+request+for+comments</font>, "
        "filtered to documents posted on or after January 1, 2008. Extracted and deduplicated "
        "parent docket IDs across both queries.",
        styles["Body"],
    ))
    story.append(Paragraph(
        "<b>Comment counting:</b> For each docket, retrieved all documents via "
        "<i>/v4/documents?filter[docketId]={id}</i>. For documents with a comment period "
        "(indicated by <i>openForComment</i> or <i>commentEndDate</i> fields), queried "
        "<i>/v4/comments?filter[commentOnId]={objectId}</i> and read <i>meta.totalElements</i>. "
        "Summed across all documents per docket.",
        styles["Body"],
    ))
    story.append(Paragraph(
        "<b>Limitations:</b> (1) The full-text search produces false positives; title-based "
        "filtering mitigates but may not eliminate all. (2) Some pre-2008 dockets appear because "
        "they were modified on regulations.gov after 2008. (3) Comment counts reflect submissions "
        "on documents with formal comment periods and may not capture all forms of public input "
        "(e.g., testimony submitted at in-person hearings).",
        styles["Body"],
    ))

    # ── Footer ───────────────────────────────────────────────────────────
    story.append(Spacer(1, 16))
    story.append(HRFlowable(width="100%", thickness=0.5, color=BORDER))
    story.append(Paragraph(
        "Prepared for stakeholder review &nbsp;|&nbsp; Data: regulations.gov API v4 "
        "&nbsp;|&nbsp; February 2026",
        styles["Note"],
    ))

    doc.build(story)
    print(f"PDF written: {PDF_PATH}")


if __name__ == "__main__":
    build_pdf()
