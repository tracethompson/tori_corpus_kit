#!/usr/bin/env python3
"""
Query regulations.gov API to find FDA dockets with public hearings (2008–present),
count public comments on each, and compute summary statistics.

Resumable via SQLite. Handles rate-limiting with exponential backoff.
"""

import csv
import json
import logging
import math
import os
import sqlite3
import statistics
import sys
import time
from datetime import datetime, timezone
from urllib.parse import urlencode

import requests

# ── Configuration ────────────────────────────────────────────────────────────
API_KEY = os.environ.get("REGULATIONS_GOV_API_KEY", "9ea9PHCYo9zkKffdT1Mf5GZaKaeKiDsdCFNnTLhs")
BASE_URL = "https://api.regulations.gov/v4"
PAGE_SIZE = 250
MAX_PAGES_PER_CYCLE = 20          # 20 × 250 = 5,000 cap
START_DATE = "2008-01-01"
DB_PATH = os.path.join(os.path.dirname(__file__), "fda_hearings.db")
CSV_PATH = os.path.join(os.path.dirname(__file__), "fda_hearings_results.csv")
LOG_EVERY = 25

SEARCH_TERMS = [
    "public hearing",
    "public hearing request for comments",
]

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("fda_hearings")

# ── HTTP helper with retry / back-off ────────────────────────────────────────
session = requests.Session()
session.headers.update({
    "X-Api-Key": API_KEY,
    "Accept": "application/json",
})


MIN_REQUEST_INTERVAL = 3.7  # seconds between requests → ~970/hr max
_last_request_time = 0.0


def _rate_gate():
    """Enforce minimum interval between requests to stay under rate limit."""
    global _last_request_time
    now = time.time()
    elapsed = now - _last_request_time
    if elapsed < MIN_REQUEST_INTERVAL:
        time.sleep(MIN_REQUEST_INTERVAL - elapsed)
    _last_request_time = time.time()


def api_get(path: str, params: dict | None = None, max_retries: int = 12) -> dict:
    """GET with exponential back-off on 429 and transient errors."""
    url = f"{BASE_URL}/{path.lstrip('/')}"
    _rate_gate()
    for attempt in range(max_retries):
        try:
            resp = session.get(url, params=params, timeout=30)
        except requests.exceptions.RequestException as exc:
            wait = min(2 ** attempt, 120)
            log.warning("Network error (%s), retrying in %ss …", exc, wait)
            time.sleep(wait)
            continue

        if resp.status_code == 200:
            return resp.json()
        if resp.status_code == 429:
            retry_after = int(resp.headers.get("Retry-After", 2 ** attempt))
            # Cap wait at 20 minutes; the Retry-After can be absurdly long
            retry_after = min(retry_after, 1200)
            log.warning("Rate-limited (429). Waiting %ds …", retry_after)
            time.sleep(retry_after)
            continue
        if resp.status_code in (500, 502, 503, 504):
            wait = min(2 ** attempt, 120)
            log.warning("Server error %s, retrying in %ss …", resp.status_code, wait)
            time.sleep(wait)
            continue
        # Auth / other hard errors
        log.error("HTTP %s — %s", resp.status_code, resp.text[:500])
        resp.raise_for_status()

    raise RuntimeError(f"Exceeded {max_retries} retries for {url}")


# ── SQLite helpers ───────────────────────────────────────────────────────────
def init_db(conn: sqlite3.Connection):
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS hearing_documents (
            document_id   TEXT PRIMARY KEY,
            object_id     TEXT,
            docket_id     TEXT,
            title         TEXT,
            posted_date   TEXT,
            document_type TEXT,
            search_term   TEXT
        );
        CREATE TABLE IF NOT EXISTS dockets (
            docket_id       TEXT PRIMARY KEY,
            docket_title    TEXT,
            docket_type     TEXT,
            date_created    TEXT,
            hearing_notice_title TEXT,
            comments_counted INTEGER DEFAULT 0,
            total_comments   INTEGER DEFAULT 0,
            flagged_fp       INTEGER DEFAULT 0
        );
        CREATE TABLE IF NOT EXISTS docket_documents (
            object_id   TEXT PRIMARY KEY,
            docket_id   TEXT,
            title       TEXT,
            doc_type    TEXT
        );
        CREATE TABLE IF NOT EXISTS comment_counts (
            object_id    TEXT PRIMARY KEY,
            docket_id    TEXT,
            comment_count INTEGER
        );
        CREATE TABLE IF NOT EXISTS cursor_state (
            key   TEXT PRIMARY KEY,
            value TEXT
        );
    """)
    conn.commit()


def get_cursor(conn, key):
    row = conn.execute("SELECT value FROM cursor_state WHERE key = ?", (key,)).fetchone()
    return row[0] if row else None


def set_cursor(conn, key, value):
    conn.execute(
        "INSERT OR REPLACE INTO cursor_state (key, value) VALUES (?, ?)",
        (key, value),
    )
    conn.commit()


# ── Helpers ──────────────────────────────────────────────────────────────────
def _normalize_datetime(dt_str: str) -> str:
    """Convert ISO datetime (e.g. 2010-03-10T19:37:34Z) to 'yyyy-MM-dd HH:mm:ss'.
    If already in that format, return as-is. If date-only, append ' 00:00:00'."""
    if not dt_str:
        return dt_str
    # Already correct format
    if len(dt_str) == 19 and "T" not in dt_str:
        return dt_str
    # ISO format with T
    s = dt_str.replace("T", " ").replace("Z", "")
    # Strip sub-second precision if present
    if "." in s:
        s = s.split(".")[0]
    # If date-only (10 chars), append time
    if len(s) == 10:
        s += " 00:00:00"
    # Ensure we have exactly 19 chars
    return s[:19]


# ── Step 1: Discover hearing-related FDA documents ──────────────────────────
def fetch_hearing_documents(conn: sqlite3.Connection):
    """Search for FDA Notices mentioning public hearings, paginate fully.

    Uses lastModifiedDate cursor (date-only) to work around the 5,000-item cap.
    """
    for term in SEARCH_TERMS:
        cursor_key = f"search_done__{term}"
        if get_cursor(conn, cursor_key):
            log.info("Search for '%s' already complete – skipping.", term)
            continue

        log.info("━━ Searching documents: searchTerm='%s' ━━", term)
        last_modified_cursor = get_cursor(conn, f"lastmod__{term}") or (START_DATE + " 00:00:00")
        total_collected = 0

        while True:
            page_num = 1
            cycle_items = 0

            while page_num <= MAX_PAGES_PER_CYCLE:
                params = {
                    "filter[agencyId]": "FDA",
                    "filter[documentType]": "Notice",
                    "filter[searchTerm]": term,
                    "filter[postedDate][ge]": START_DATE,
                    "filter[lastModifiedDate][ge]": _normalize_datetime(last_modified_cursor),
                    "sort": "lastModifiedDate",
                    "page[size]": PAGE_SIZE,
                    "page[number]": page_num,
                }
                data = api_get("documents", params)
                items = data.get("data", [])
                if not items:
                    break

                for item in items:
                    attrs = item.get("attributes", {})
                    doc_id = item.get("id", "")
                    obj_id = attrs.get("objectId", doc_id)
                    docket_id = attrs.get("docketId", "")
                    title = attrs.get("title", "")
                    posted = attrs.get("postedDate", "")
                    doc_type = attrs.get("documentType", "")
                    last_mod = attrs.get("lastModifiedDate", "")

                    conn.execute(
                        """INSERT OR IGNORE INTO hearing_documents
                           (document_id, object_id, docket_id, title, posted_date, document_type, search_term)
                           VALUES (?, ?, ?, ?, ?, ?, ?)""",
                        (doc_id, obj_id, docket_id, title, posted, doc_type, term),
                    )

                    # Track the max lastModifiedDate we've seen (date-only for cursor)
                    last_mod_date = _normalize_datetime(last_mod)
                    if last_mod_date and last_mod_date > last_modified_cursor:
                        last_modified_cursor = last_mod_date

                conn.commit()
                cycle_items += len(items)
                total_collected += len(items)
                log.info("  page %d  →  %d items (cycle %d, total %d)",
                         page_num, len(items), cycle_items, total_collected)

                if len(items) < PAGE_SIZE:
                    break
                page_num += 1
                time.sleep(0.15)  # gentle pacing

            set_cursor(conn, f"lastmod__{term}", last_modified_cursor)

            # If we didn't fill the full 5,000-item cycle, we're done
            if cycle_items < MAX_PAGES_PER_CYCLE * PAGE_SIZE:
                break
            log.info("  ↻ cursor pagination — resuming from lastModifiedDate=%s", last_modified_cursor)

        set_cursor(conn, cursor_key, "1")
        log.info("Search for '%s' complete. %d documents collected.", term, total_collected)


def build_docket_list(conn: sqlite3.Connection) -> list[str]:
    """Deduplicate docket IDs from hearing documents, populate dockets table."""
    rows = conn.execute(
        "SELECT DISTINCT docket_id FROM hearing_documents WHERE docket_id != ''"
    ).fetchall()
    docket_ids = [r[0] for r in rows]

    for did in docket_ids:
        # Pick one hearing-notice title for the docket
        title_row = conn.execute(
            "SELECT title FROM hearing_documents WHERE docket_id = ? LIMIT 1", (did,)
        ).fetchone()
        hearing_title = title_row[0] if title_row else ""
        conn.execute(
            """INSERT OR IGNORE INTO dockets
               (docket_id, hearing_notice_title)
               VALUES (?, ?)""",
            (did, hearing_title),
        )
    conn.commit()
    log.info("Unique dockets: %d", len(docket_ids))
    return docket_ids


# ── Step 1b: Fetch docket metadata ──────────────────────────────────────────
def fetch_docket_metadata(conn: sqlite3.Connection, docket_ids: list[str]):
    """Get title, type, and creation date for each docket."""
    need = [
        d for d in docket_ids
        if conn.execute(
            "SELECT docket_title FROM dockets WHERE docket_id = ?", (d,)
        ).fetchone()[0] is None
    ]
    log.info("Fetching metadata for %d dockets …", len(need))
    for i, did in enumerate(need, 1):
        try:
            data = api_get(f"dockets/{did}")
            attrs = data.get("data", {}).get("attributes", {})
            conn.execute(
                """UPDATE dockets
                   SET docket_title = ?, docket_type = ?, date_created = ?
                   WHERE docket_id = ?""",
                (
                    attrs.get("title", ""),
                    attrs.get("docketType", ""),
                    attrs.get("modifyDate", attrs.get("effectiveDate", "")),
                    did,
                ),
            )
        except Exception as exc:
            log.warning("Could not fetch metadata for %s: %s", did, exc)
        if i % LOG_EVERY == 0:
            conn.commit()
            log.info("  metadata: %d / %d", i, len(need))
        time.sleep(0.15)
    conn.commit()


# ── Step 2: Count comments per docket ───────────────────────────────────────
# Document types that typically receive comments (skip Supporting & Related Material)
COMMENTABLE_DOC_TYPES = {"Notice", "Proposed Rule", "Rule"}


def count_comments_for_docket(conn: sqlite3.Connection, docket_id: str) -> int:
    """Count comments per docket via the /comments endpoint.

    1. Fetch all documents for the docket.
    2. For each commentable document (not Supporting & Related Material),
       query /comments?filter[commentOnId]={objectId} and read meta.totalElements.
    3. Sum across all documents.
    """
    # Check if already done
    row = conn.execute(
        "SELECT comments_counted, total_comments FROM dockets WHERE docket_id = ?",
        (docket_id,),
    ).fetchone()
    if row and row[0]:
        return row[1]

    # Get all documents in the docket
    doc_object_ids = []  # (objectId, docType, has_comment_period)
    last_mod_cursor = "1970-01-01 00:00:00"
    while True:
        page_num = 1
        cycle_items = 0
        while page_num <= MAX_PAGES_PER_CYCLE:
            params = {
                "filter[docketId]": docket_id,
                "filter[lastModifiedDate][ge]": _normalize_datetime(last_mod_cursor),
                "sort": "lastModifiedDate",
                "page[size]": PAGE_SIZE,
                "page[number]": page_num,
            }
            data = api_get("documents", params)
            items = data.get("data", [])
            if not items:
                break
            for item in items:
                attrs = item.get("attributes", {})
                obj_id = attrs.get("objectId", item.get("id", ""))
                doc_type = attrs.get("documentType", "")
                last_mod = _normalize_datetime(attrs.get("lastModifiedDate", ""))
                has_cp = bool(attrs.get("commentEndDate") or attrs.get("openForComment"))
                doc_object_ids.append((obj_id, doc_type, has_cp))
                if last_mod and last_mod > last_mod_cursor:
                    last_mod_cursor = last_mod
            cycle_items += len(items)
            if len(items) < PAGE_SIZE:
                break
            page_num += 1
        if cycle_items < MAX_PAGES_PER_CYCLE * PAGE_SIZE:
            break

    # Count comments only on documents that accept comments
    total = 0
    for obj_id, doc_type, has_comment_period in doc_object_ids:
        if not has_comment_period:
            continue
        # Check cache
        cached = conn.execute(
            "SELECT comment_count FROM comment_counts WHERE object_id = ?", (obj_id,)
        ).fetchone()
        if cached is not None:
            total += cached[0]
            continue

        try:
            data = api_get("comments", {
                "filter[commentOnId]": obj_id,
                "page[size]": 5,
            })
            count = data.get("meta", {}).get("totalElements", 0)
        except Exception as exc:
            log.warning("  comment count failed for %s/%s: %s", docket_id, obj_id, exc)
            count = 0

        conn.execute(
            "INSERT OR REPLACE INTO comment_counts (object_id, docket_id, comment_count) VALUES (?, ?, ?)",
            (obj_id, docket_id, count),
        )
        total += count

    conn.execute(
        "UPDATE dockets SET comments_counted = 1, total_comments = ? WHERE docket_id = ?",
        (total, docket_id),
    )
    conn.commit()
    return total


# ── False-positive flagging ─────────────────────────────────────────────────
HEARING_KEYWORDS = [
    "public hearing",
    "hearing; request for comments",
    "request for comments; hearing",
    "notice of hearing",
    "public meeting",
]


def flag_false_positives(conn: sqlite3.Connection):
    """Flag dockets whose hearing-notice titles don't look like actual hearings."""
    rows = conn.execute(
        "SELECT docket_id, hearing_notice_title FROM dockets"
    ).fetchall()
    flagged = 0
    for docket_id, title in rows:
        title_lower = (title or "").lower()
        looks_like_hearing = any(kw in title_lower for kw in HEARING_KEYWORDS)
        fp = 0 if looks_like_hearing else 1
        conn.execute(
            "UPDATE dockets SET flagged_fp = ? WHERE docket_id = ?",
            (fp, docket_id),
        )
        if fp:
            flagged += 1
    conn.commit()
    log.info("Flagged %d / %d dockets as potential false positives.", flagged, len(rows))


# ── Output & statistics ─────────────────────────────────────────────────────
def export_csv(conn: sqlite3.Connection):
    rows = conn.execute(
        """SELECT docket_id, docket_title, docket_type, date_created,
                  total_comments, hearing_notice_title, flagged_fp
           FROM dockets ORDER BY total_comments DESC"""
    ).fetchall()
    with open(CSV_PATH, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow([
            "docket_id", "docket_title", "docket_type", "date_created",
            "total_comments", "hearing_notice_title", "flagged_fp",
        ])
        for r in rows:
            w.writerow(r)
    log.info("CSV written → %s  (%d rows)", CSV_PATH, len(rows))


def percentile(sorted_data, p):
    """Compute the p-th percentile (0–100) via linear interpolation."""
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
    """What percent of values are ≤ value."""
    n = len(sorted_data)
    if n == 0:
        return 0
    count_below = sum(1 for v in sorted_data if v <= value)
    return (count_below / n) * 100


def print_statistics(conn: sqlite3.Connection):
    rows = conn.execute(
        "SELECT docket_id, docket_title, total_comments FROM dockets ORDER BY total_comments"
    ).fetchall()
    counts = [r[2] for r in rows]
    n = len(counts)

    if n == 0:
        log.warning("No dockets found — nothing to report.")
        return

    med = statistics.median(counts)
    mean = statistics.mean(counts)
    p75 = percentile(counts, 75)
    p90 = percentile(counts, 90)
    p95 = percentile(counts, 95)
    p99 = percentile(counts, 99)
    target_prank = percentile_rank(counts, 6950)

    print("\n" + "=" * 72)
    print("  FDA PUBLIC-HEARING DOCKETS — COMMENT STATISTICS (2008–present)")
    print("=" * 72)
    print(f"  Total dockets found:        {n}")
    print(f"  Mean comment count:         {mean:,.1f}")
    print(f"  Median comment count:       {med:,.1f}")
    print(f"  75th percentile:            {p75:,.1f}")
    print(f"  90th percentile:            {p90:,.1f}")
    print(f"  95th percentile:            {p95:,.1f}")
    print(f"  99th percentile:            {p99:,.1f}")
    print(f"  6,950 comments → percentile rank: {target_prank:.1f}%")
    print("-" * 72)
    print("  Top 10 dockets by comment count:")
    top10 = sorted(rows, key=lambda r: r[2], reverse=True)[:10]
    for i, (did, title, cnt) in enumerate(top10, 1):
        short_title = (title or "")[:60]
        print(f"    {i:>2}. {cnt:>8,}  {did:<22s}  {short_title}")
    print("=" * 72)

    # Also report false-positive counts
    fp_count = conn.execute("SELECT COUNT(*) FROM dockets WHERE flagged_fp = 1").fetchone()[0]
    non_fp = n - fp_count
    print(f"\n  Note: {fp_count} dockets flagged as potential false positives.")
    print(f"  If excluding them, {non_fp} dockets remain.\n")

    # Recompute stats excluding false positives
    clean_rows = conn.execute(
        "SELECT total_comments FROM dockets WHERE flagged_fp = 0 ORDER BY total_comments"
    ).fetchall()
    clean_counts = [r[0] for r in clean_rows]
    if clean_counts:
        print("  ── Stats excluding flagged false positives ──")
        print(f"  Dockets:                    {len(clean_counts)}")
        print(f"  Mean comment count:         {statistics.mean(clean_counts):,.1f}")
        print(f"  Median comment count:       {statistics.median(clean_counts):,.1f}")
        print(f"  75th percentile:            {percentile(clean_counts, 75):,.1f}")
        print(f"  90th percentile:            {percentile(clean_counts, 90):,.1f}")
        print(f"  95th percentile:            {percentile(clean_counts, 95):,.1f}")
        print(f"  99th percentile:            {percentile(clean_counts, 99):,.1f}")
        clean_prank = percentile_rank(clean_counts, 6950)
        print(f"  6,950 comments → percentile rank: {clean_prank:.1f}%")
        print()


# ── Main ─────────────────────────────────────────────────────────────────────
def main():
    log.info("Database: %s", DB_PATH)
    conn = sqlite3.connect(DB_PATH)
    init_db(conn)

    # Quick auth check
    log.info("Testing API connectivity …")
    try:
        test = api_get("documents", {
            "filter[agencyId]": "FDA",
            "page[size]": 5,
        })
        total = test.get("meta", {}).get("totalElements", "?")
        log.info("API OK — FDA documents total: %s", total)
    except Exception as exc:
        log.error("API auth/connection failed: %s", exc)
        log.error("Check your API key and network. GSA may have restricted access (Aug 2025).")
        sys.exit(1)

    # Step 1: discover hearing documents
    fetch_hearing_documents(conn)
    docket_ids = build_docket_list(conn)

    # Step 1b: docket metadata
    fetch_docket_metadata(conn, docket_ids)

    # Step 2: count comments per docket
    remaining = [
        d for d in docket_ids
        if not conn.execute(
            "SELECT comments_counted FROM dockets WHERE docket_id = ? AND comments_counted = 1",
            (d,),
        ).fetchone()
    ]
    log.info("Comment counting: %d already done, %d remaining.",
             len(docket_ids) - len(remaining), len(remaining))

    for i, did in enumerate(remaining, 1):
        total = count_comments_for_docket(conn, did)
        if i % LOG_EVERY == 0:
            log.info("  progress: %d / %d dockets counted  (latest: %s → %d comments)",
                     i, len(remaining), did, total)

    # Flag false positives
    flag_false_positives(conn)

    # Output
    export_csv(conn)
    print_statistics(conn)

    conn.close()
    log.info("Done.")


if __name__ == "__main__":
    main()
