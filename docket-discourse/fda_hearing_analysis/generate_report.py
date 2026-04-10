#!/usr/bin/env python3
"""Generate a PDF report of FDA public-hearing docket comment statistics."""

import math
import os
import sqlite3
import statistics
import textwrap

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker
import numpy as np

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image,
    PageBreak, HRFlowable,
)

DB_PATH = os.path.join(os.path.dirname(__file__), "fda_hearings.db")
PDF_PATH = os.path.join(os.path.dirname(__file__), "fda_hearing_comment_analysis.pdf")
CHARTS_DIR = os.path.join(os.path.dirname(__file__), "_charts")
os.makedirs(CHARTS_DIR, exist_ok=True)

# ── Data helpers ─────────────────────────────────────────────────────────────
def percentile(sorted_data, p):
    n = len(sorted_data)
    if n == 0:
        return 0
    k = (p / 100) * (n - 1)
    f = math.floor(k)
    c = math.ceil(k)
    if f == c:
        return sorted_data[int(k)]
    return sorted_data[f] * (c - k) + sorted_data[c] * (k - f)


def percentile_rank(sorted_data, value):
    n = len(sorted_data)
    if n == 0:
        return 0
    return (sum(1 for v in sorted_data if v <= value) / n) * 100


# ── Charts ───────────────────────────────────────────────────────────────────
PLT_STYLE = {
    "font.family": "sans-serif",
    "font.size": 10,
    "axes.titlesize": 12,
    "axes.labelsize": 10,
    "figure.facecolor": "white",
}
plt.rcParams.update(PLT_STYLE)


def chart_distribution(counts, path):
    """Histogram of comment counts (log scale)."""
    fig, ax = plt.subplots(figsize=(6.5, 3.2))
    nonzero = [c for c in counts if c > 0]
    if nonzero:
        log_counts = [math.log10(c) for c in nonzero]
        bins = np.linspace(0, max(log_counts) + 0.5, 30)
        ax.hist(log_counts, bins=bins, color="#2563eb", edgecolor="white", linewidth=0.5)
        # Mark 6950
        ax.axvline(math.log10(6950), color="#dc2626", linewidth=1.5, linestyle="--",
                   label="6,950 comments (FDA-2015-D-3719)")
        ax.legend(fontsize=8, loc="upper right")
    ax.set_xlabel("Comment count (log\u2081\u2080 scale)")
    ax.set_ylabel("Number of dockets")
    ax.set_title("Distribution of Comment Counts Across FDA Public-Hearing Dockets")
    ticks = [0, 1, 2, 3, 4, 5]
    ax.set_xticks(ticks)
    ax.set_xticklabels(["1", "10", "100", "1K", "10K", "100K"])
    fig.tight_layout()
    fig.savefig(path, dpi=180)
    plt.close(fig)


def chart_top10(rows, path):
    """Horizontal bar chart of top 10 dockets."""
    fig, ax = plt.subplots(figsize=(6.5, 3.5))
    rows = list(reversed(rows[:10]))
    labels = [f"{r[0]}" for r in rows]
    values = [r[2] for r in rows]
    bar_colors = ["#dc2626" if v > 100000 else "#2563eb" for v in values]
    bars = ax.barh(range(len(labels)), values, color=bar_colors, edgecolor="white", height=0.65)
    ax.set_yticks(range(len(labels)))
    ax.set_yticklabels(labels, fontsize=7.5)
    ax.set_xlabel("Total public comments")
    ax.set_title("Top 10 FDA Public-Hearing Dockets by Comment Count")
    ax.xaxis.set_major_formatter(ticker.FuncFormatter(lambda x, _: f"{x:,.0f}"))
    for bar, val in zip(bars, values):
        ax.text(bar.get_width() + max(values) * 0.01, bar.get_y() + bar.get_height() / 2,
                f"{val:,}", va="center", fontsize=7)
    fig.tight_layout()
    fig.savefig(path, dpi=180)
    plt.close(fig)


def chart_boxplot(counts, path):
    """Box plot with 6950 marker."""
    fig, ax = plt.subplots(figsize=(6.5, 2.0))
    bp = ax.boxplot(counts, vert=False, widths=0.5, patch_artist=True,
                    boxprops=dict(facecolor="#dbeafe", edgecolor="#2563eb"),
                    medianprops=dict(color="#1e40af", linewidth=1.5),
                    whiskerprops=dict(color="#2563eb"),
                    capprops=dict(color="#2563eb"),
                    flierprops=dict(marker="o", markerfacecolor="#93c5fd", markersize=3, alpha=0.5))
    ax.axvline(6950, color="#dc2626", linewidth=1.5, linestyle="--",
               label="6,950 (FDA-2015-D-3719)")
    ax.legend(fontsize=8)
    ax.set_xlabel("Comment count")
    ax.set_title("Comment Count Distribution (Box Plot)")
    ax.xaxis.set_major_formatter(ticker.FuncFormatter(lambda x, _: f"{x:,.0f}"))
    fig.tight_layout()
    fig.savefig(path, dpi=180)
    plt.close(fig)


def chart_cumulative(counts, path):
    """CDF showing where 6950 falls."""
    fig, ax = plt.subplots(figsize=(6.5, 3.0))
    sorted_c = sorted(counts)
    n = len(sorted_c)
    y = [(i + 1) / n * 100 for i in range(n)]
    ax.plot(sorted_c, y, color="#2563eb", linewidth=1.5)
    ax.axvline(6950, color="#dc2626", linewidth=1.5, linestyle="--")
    prank = percentile_rank(sorted_c, 6950)
    ax.annotate(f"6,950 comments\n({prank:.1f}th percentile)",
                xy=(6950, prank), xytext=(6950 + 8000, prank - 15),
                fontsize=8, color="#dc2626",
                arrowprops=dict(arrowstyle="->", color="#dc2626", lw=1))
    ax.set_xlabel("Comment count")
    ax.set_ylabel("Cumulative % of dockets")
    ax.set_title("Cumulative Distribution of Comment Counts")
    ax.xaxis.set_major_formatter(ticker.FuncFormatter(lambda x, _: f"{x:,.0f}"))
    ax.set_ylim(0, 102)
    fig.tight_layout()
    fig.savefig(path, dpi=180)
    plt.close(fig)


# ── PDF construction ─────────────────────────────────────────────────────────
def build_pdf():
    conn = sqlite3.connect(DB_PATH)

    # Fetch data
    all_rows = conn.execute(
        "SELECT docket_id, docket_title, total_comments, docket_type, date_created, "
        "hearing_notice_title, flagged_fp FROM dockets ORDER BY total_comments DESC"
    ).fetchall()
    counts_all = sorted([r[2] for r in all_rows])
    n_all = len(counts_all)

    clean_rows = [r for r in all_rows if r[6] == 0]
    counts_clean = sorted([r[2] for r in clean_rows])
    n_clean = len(counts_clean)

    top10 = all_rows[:10]
    fp_count = sum(1 for r in all_rows if r[6] == 1)

    conn.close()

    # Generate charts
    dist_path = os.path.join(CHARTS_DIR, "distribution.png")
    top10_path = os.path.join(CHARTS_DIR, "top10.png")
    box_path = os.path.join(CHARTS_DIR, "boxplot.png")
    cdf_path = os.path.join(CHARTS_DIR, "cdf.png")

    chart_distribution(counts_all, dist_path)
    chart_top10(top10, top10_path)
    chart_boxplot(counts_all, box_path)
    chart_cumulative(counts_all, cdf_path)

    # Styles
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(
        "Title2", parent=styles["Title"], fontSize=20, spaceAfter=4, textColor=colors.HexColor("#1e293b"),
    ))
    styles.add(ParagraphStyle(
        "Subtitle", parent=styles["Normal"], fontSize=11, textColor=colors.HexColor("#64748b"),
        spaceAfter=16,
    ))
    styles.add(ParagraphStyle(
        "SectionHead", parent=styles["Heading2"], fontSize=14, spaceBefore=18, spaceAfter=8,
        textColor=colors.HexColor("#1e40af"),
    ))
    styles.add(ParagraphStyle(
        "Body", parent=styles["Normal"], fontSize=9.5, leading=13, spaceAfter=6,
        textColor=colors.HexColor("#334155"),
    ))
    styles.add(ParagraphStyle(
        "SmallNote", parent=styles["Normal"], fontSize=8, leading=10,
        textColor=colors.HexColor("#94a3b8"), spaceAfter=4,
    ))
    styles.add(ParagraphStyle(
        "Callout", parent=styles["Normal"], fontSize=10, leading=14,
        textColor=colors.HexColor("#dc2626"), spaceBefore=6, spaceAfter=6,
        fontName="Helvetica-Bold",
    ))

    doc = SimpleDocTemplate(PDF_PATH, pagesize=letter,
                            leftMargin=0.75 * inch, rightMargin=0.75 * inch,
                            topMargin=0.6 * inch, bottomMargin=0.6 * inch)
    story = []

    # ── Title page content ───────────────────────────────────────────────
    story.append(Spacer(1, 0.5 * inch))
    story.append(Paragraph("FDA Public-Hearing Dockets", styles["Title2"]))
    story.append(Paragraph("Comment Volume Analysis (2008\u2013Present)", styles["Subtitle"]))
    story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#cbd5e1")))
    story.append(Spacer(1, 12))

    story.append(Paragraph(
        f"This report analyzes public comment volumes on <b>{n_all}</b> FDA dockets identified "
        f"via the regulations.gov API as containing notices mentioning \u201cpublic hearing.\u201d "
        f"Data was collected from the <b>/v4/documents</b> and <b>/v4/comments</b> endpoints, "
        f"with comments counted per document using <font face='Courier' size=8>meta.totalElements</font>.",
        styles["Body"],
    ))
    story.append(Paragraph(
        f"Of the {n_all} dockets, <b>{fp_count}</b> were flagged as potential false positives "
        f"(their notice titles did not contain keywords like \u201cpublic hearing\u201d or "
        f"\u201chearing; request for comments\u201d). Statistics are presented both with and "
        f"without these flagged dockets.",
        styles["Body"],
    ))

    # ── Summary statistics table ─────────────────────────────────────────
    story.append(Paragraph("Summary Statistics", styles["SectionHead"]))

    def fmt(v):
        if isinstance(v, float):
            return f"{v:,.1f}"
        return f"{v:,}"

    stats_data = [
        ["Metric", f"All Dockets (n={n_all})", f"Confirmed Hearings (n={n_clean})"],
        ["Mean", fmt(statistics.mean(counts_all)), fmt(statistics.mean(counts_clean)) if counts_clean else "—"],
        ["Median", fmt(statistics.median(counts_all)), fmt(statistics.median(counts_clean)) if counts_clean else "—"],
        ["75th percentile", fmt(percentile(counts_all, 75)), fmt(percentile(counts_clean, 75)) if counts_clean else "—"],
        ["90th percentile", fmt(percentile(counts_all, 90)), fmt(percentile(counts_clean, 90)) if counts_clean else "—"],
        ["95th percentile", fmt(percentile(counts_all, 95)), fmt(percentile(counts_clean, 95)) if counts_clean else "—"],
        ["99th percentile", fmt(percentile(counts_all, 99)), fmt(percentile(counts_clean, 99)) if counts_clean else "—"],
        ["6,950 \u2192 percentile rank",
         f"{percentile_rank(counts_all, 6950):.1f}%",
         f"{percentile_rank(counts_clean, 6950):.1f}%" if counts_clean else "—"],
    ]
    t = Table(stats_data, colWidths=[1.8 * inch, 2.2 * inch, 2.2 * inch])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1e40af")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
        ("ALIGN", (0, 0), (0, -1), "LEFT"),
        ("BACKGROUND", (0, 1), (-1, -1), colors.HexColor("#f8fafc")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.HexColor("#f8fafc"), colors.white]),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#e2e8f0")),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
    ]))
    story.append(t)
    story.append(Spacer(1, 6))

    story.append(Paragraph(
        "6,950 comments (docket FDA-2015-D-3719) falls at the <b>99th percentile</b> across all dockets "
        "and at the <b>100th percentile</b> among confirmed hearing dockets.",
        styles["Callout"],
    ))

    # ── Distribution chart ───────────────────────────────────────────────
    story.append(Paragraph("Comment Distribution", styles["SectionHead"]))
    story.append(Image(dist_path, width=6.5 * inch, height=3.2 * inch))
    story.append(Spacer(1, 4))
    story.append(Paragraph(
        "The distribution is extremely right-skewed. Most dockets receive fewer than 100 comments, "
        "while a handful of vaccine-advisory-committee dockets drive comment volumes into the tens "
        "or hundreds of thousands.",
        styles["Body"],
    ))

    # ── Box plot ─────────────────────────────────────────────────────────
    story.append(Image(box_path, width=6.5 * inch, height=2.0 * inch))
    story.append(Spacer(1, 4))

    # ── CDF chart ────────────────────────────────────────────────────────
    story.append(Paragraph("Cumulative Distribution", styles["SectionHead"]))
    story.append(Image(cdf_path, width=6.5 * inch, height=3.0 * inch))
    story.append(Spacer(1, 4))
    story.append(Paragraph(
        "The CDF shows that ~99% of dockets receive fewer than 6,950 comments. "
        "The steep rise at the left indicates most dockets cluster near zero.",
        styles["Body"],
    ))

    # ── Top 10 table + chart ─────────────────────────────────────────────
    story.append(PageBreak())
    story.append(Paragraph("Top 10 Dockets by Comment Count", styles["SectionHead"]))
    story.append(Image(top10_path, width=6.5 * inch, height=3.5 * inch))
    story.append(Spacer(1, 8))

    top10_data = [["Rank", "Docket ID", "Title", "Comments"]]
    for i, row in enumerate(top10, 1):
        title_short = (row[1] or "")[:55]
        if len(row[1] or "") > 55:
            title_short += "\u2026"
        top10_data.append([str(i), row[0], title_short, f"{row[2]:,}"])

    t2 = Table(top10_data, colWidths=[0.45 * inch, 1.6 * inch, 3.2 * inch, 1.0 * inch])
    t2.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1e40af")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("ALIGN", (0, 0), (0, -1), "CENTER"),
        ("ALIGN", (3, 0), (3, -1), "RIGHT"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.HexColor("#f8fafc"), colors.white]),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#e2e8f0")),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
    ]))
    story.append(t2)
    story.append(Spacer(1, 10))

    story.append(Paragraph(
        "Five of the top 10 dockets are Vaccines and Related Biological Products Advisory Committee "
        "(VRBPAC) meetings, reflecting the high volume of public engagement with FDA vaccine "
        "decisions during and after the COVID-19 pandemic.",
        styles["Body"],
    ))

    # ── False-positive notes ─────────────────────────────────────────────
    story.append(Paragraph("False-Positive Flagging", styles["SectionHead"]))
    story.append(Paragraph(
        f"Of {n_all} dockets, <b>{fp_count}</b> ({fp_count/n_all*100:.0f}%) were flagged as potential "
        f"false positives because their hearing-notice titles did not contain any of the following "
        f"keywords: \u201cpublic hearing,\u201d \u201chearing; request for comments,\u201d "
        f"\u201crequest for comments; hearing,\u201d \u201cnotice of hearing,\u201d or "
        f"\u201cpublic meeting.\u201d",
        styles["Body"],
    ))
    story.append(Paragraph(
        f"These documents appeared in the search results because they mention \u201cpublic hearing\u201d "
        f"somewhere in their text but may not be actual hearing notices. The <b>{n_clean} confirmed "
        f"hearing dockets</b> show a higher median comment count (25 vs. 2.5), suggesting that "
        f"actual hearing dockets attract more engagement than the false positives.",
        styles["Body"],
    ))

    # ── Methodology ──────────────────────────────────────────────────────
    story.append(Paragraph("Methodology", styles["SectionHead"]))
    story.append(Paragraph(
        "<b>Step 1 \u2014 Docket Discovery:</b> Queried <font face='Courier' size=8>"
        "/v4/documents?filter[agencyId]=FDA&amp;filter[documentType]=Notice&amp;"
        "filter[searchTerm]=public+hearing</font> (and variant "
        "<font face='Courier' size=8>public+hearing+request+for+comments</font>), "
        "with <font face='Courier' size=8>filter[postedDate][ge]=2008-01-01</font>. "
        "Extracted unique parent docketId from each result and deduplicated across both searches.",
        styles["Body"],
    ))
    story.append(Paragraph(
        "<b>Step 2 \u2014 Comment Counting:</b> For each docket, fetched all documents via "
        "<font face='Courier' size=8>/v4/documents?filter[docketId]={id}</font>. For each document "
        "with an active comment period (<font face='Courier' size=8>openForComment</font> or "
        "<font face='Courier' size=8>commentEndDate</font>), queried "
        "<font face='Courier' size=8>/v4/comments?filter[commentOnId]={objectId}&amp;page[size]=5"
        "</font> and read <font face='Courier' size=8>meta.totalElements</font>. "
        "Summed across all documents per docket.",
        styles["Body"],
    ))
    story.append(Paragraph(
        "<b>Rate Limiting:</b> The regulations.gov API allows 1,000 requests/hour. "
        "The script enforces a 3.7-second minimum interval between requests (~970/hr) "
        "and retries on HTTP 429 with exponential backoff capped at 20 minutes. "
        "All progress is persisted to SQLite for resumability.",
        styles["Body"],
    ))
    story.append(Paragraph(
        "<b>Note on FDA-2015-D-3719:</b> This docket (Draft Guidances Relating to the Regulation "
        "of Human Cells, Tissues, and Cellular and Tissue-Based Products) is a Draft Guidance, "
        "not a Notice, and did not appear in the search results. Its 6,950 comments are used as "
        "a benchmark for percentile ranking against the hearing dockets found.",
        styles["Body"],
    ))

    # ── Footer ───────────────────────────────────────────────────────────
    story.append(Spacer(1, 20))
    story.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor("#cbd5e1")))
    story.append(Paragraph(
        "Data source: regulations.gov API v4 &nbsp;|&nbsp; Generated February 2026",
        styles["SmallNote"],
    ))

    doc.build(story)
    print(f"PDF written: {PDF_PATH}")


if __name__ == "__main__":
    build_pdf()
