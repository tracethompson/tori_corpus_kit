# docket-discourse Pipeline Flow

This document summarizes the end-to-end processing flow for the FDA-2015-D-3719 public comment analysis suite and highlights the new manual attachment recovery tool.

## Phase Overview

1. **Data Collection (Phase 1)**
   - `scrapers/regulations_scraper.py` fetches comments via the regulations.gov v4 API, follows metadata/attachment links, performs live classification, and saves JSON/CSV/searchable text along with checkpoints.
   - `scrapers/docket_search.py` discovers related dockets for contextual analysis.
   - `scrapers/baseline_calculator.py` samples hundreds of FDA proceedings to benchmark comment volumes and produces comparison plots/reports.

2. **Analysis (Phase 2)**
   - `analyzers/corpus_analyzer.py` runs three-track NLP (all/personal/technical) to emit word/phrase stats and possessive-language studies.
   - `analyzers/frame_detector.py` applies the four-frame model, outputs distributions/crosstabs, and surfaces potential new indicators.
   - `analyzers/stakeholder_classifier.py` labels submitters by stakeholder category with confidence scoring, plus manual-review exports.
   - `analyzers/temporal_mapper.py` builds submission timelines, MinHash/LSH duplicate clusters, and unique argument metrics.
   - `visualization/citation_extractor.py` pulls CFR/PHSA/guidance citations with stakeholder cross-tabs.

3. **Export & Visualization (Phase 3)**
   - `visualization/chart_generator.py` converts processed outputs into publication-ready PNG/PDF charts.
   - `utils/export_formatter.py` creates methodology docs, MLA citations, DOCX/LaTeX tables, and themed quote packs under `data/outputs`.

## Manual Attachment Recovery Tool

Some comments say “see attached” even when the API payload lacks `attachments`. The new `scrapers/attachment_fetcher.py` tool addresses this gap by:

1. Scanning `data/raw/comments.json` for comments without attachments but whose text contains phrases such as “see attached,” “attachment,” or “enclosed.”
2. Attempting to download files from the public downloads site using URL patterns like `https://downloads.regulations.gov/<comment_id>/attachment_<n>.pdf`.
3. Storing recovered files in `data/raw/manual_attachments/<comment_id>/`.
4. Updating each comment’s `attachments` array and `full_text` with extracted PDF text (via PyPDF2 when available) so downstream analyzers can incorporate the attachment content.
5. Writing a summary to `data/processed/manual_attachment_report.json` and refreshing `data/raw/comments.json` if any records were augmented.

### Running the Tool

```bash
python main.py --tool attachments
```

Run this after the main scraper completes to backfill missing attachments. The command is idempotent: it skips files that were already downloaded and stops probing once a sequential attachment slot is empty.

If additional attachment cues emerge (e.g., new keywords or alternative URL formats), update `AttachmentFetcher.KEYWORD_PATTERNS` or `AttachmentFetcher.EXTENSIONS` accordingly.
