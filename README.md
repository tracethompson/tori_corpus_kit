# Tori Corpus Kit

An analysis toolkit for studying FDA public comments on docket **FDA-2015-D-3719** — the regulatory proposal on *Human Cells, Tissues, and Cellular and Tissue-Based Products from Adipose Tissue*.

This toolkit downloads, classifies, and analyzes ~6,950 public comments submitted to the FDA, producing searchable text files, statistical breakdowns, and publication-ready tables and figures.

---

## Where to Find Things

### Searching and Reading Comments

| What you want | Where to look |
|---|---|
| All comments as readable text | `docket-discourse/data/raw/comments_searchable_ALL.txt` |
| Only personal stories | `docket-discourse/data/raw/comments_searchable_personal_narratives.txt` |
| Only technical/legal submissions | `docket-discourse/data/raw/comments_searchable_technical_documents.txt` |
| Only organizational submissions | `docket-discourse/data/raw/comments_searchable_organizational.txt` |
| Full structured data (JSON) | `docket-discourse/data/raw/comments.json` |
| Spreadsheet format (CSV) | `docket-discourse/data/raw/comments.csv` |
| PDF attachments | `docket-discourse/data/raw/manual_attachments/` |

### Analysis Results

| What you want | Where to look |
|---|---|
| Word frequency counts | `docket-discourse/data/processed/word_freq_*.csv` |
| Rhetorical framing analysis | `docket-discourse/data/processed/frame_analysis.csv` |
| Stakeholder classifications | `docket-discourse/data/processed/stakeholder_*.csv` |
| Duplicate / form letter detection | `docket-discourse/data/processed/duplicate_comment_groups.csv` |
| Extracted regulatory citations | `docket-discourse/data/processed/citations_*.csv` |

### Publication-Ready Outputs

| What you want | Where to look |
|---|---|
| Formatted tables (Word & LaTeX) | `docket-discourse/data/outputs/tables/` |
| Charts and figures (300dpi PNG & PDF) | `docket-discourse/data/outputs/figures/` |
| Curated quotes with MLA citations | `docket-discourse/data/outputs/quotes/` |
| Auto-generated methodology section | `docket-discourse/data/outputs/methodology.md` |

### Documentation

| What you want | Where to look |
|---|---|
| Technical documentation | `docket-discourse/README.md` |
| Processing pipeline details | `docket-discourse/docs/PROCESS.md` |

---

## Directory Overview

```
tori_corpus_kit/
└── docket-discourse/          Main application
    ├── main.py                Entry point - run this to start
    ├── scrapers/              Downloads comments from regulations.gov
    ├── analyzers/             Classifies and analyzes comment text
    ├── visualization/         Generates charts and extracts citations
    ├── utils/                 Configuration and helper utilities
    ├── dictionaries/          Editable keyword lists for classification
    ├── data/
    │   ├── raw/               Downloaded comments and attachments
    │   ├── processed/         Analysis output files
    │   └── outputs/           Publication-ready tables, figures, quotes
    ├── tests/                 Automated tests
    └── docs/                  Additional documentation
```

---

## Running the Toolkit

### First-Time Setup

1. Install Python 3.9 or higher
2. Get a free API key from [regulations.gov](https://api.regulations.gov)
3. Run the setup commands:

```bash
cd docket-discourse
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python -m spacy download en_core_web_sm
export REGULATIONS_GOV_API_KEY="your-key-here"
```

### Common Commands

```bash
# Run everything start to finish
python main.py --full

# Run one phase at a time
python main.py --phase 1    # Download comments
python main.py --phase 2    # Analyze comments
python main.py --phase 3    # Generate outputs

# Run a single tool
python main.py --tool scraper         # Download comments
python main.py --tool scraper --limit 100   # Test with just 100 comments
python main.py --tool frames          # Rhetorical frame analysis
python main.py --tool stakeholder     # Stakeholder classification
python main.py --tool export          # Generate publication files
```

See `docket-discourse/README.md` for the full list of tools and options.

---

## Customization

You can adjust how comments are classified by editing two JSON files in `docket-discourse/dictionaries/`:

- **`stakeholder_keywords.json`** — Keywords used to identify author types (patient, provider, industry, etc.)
- **`technical_terms.json`** — Domain-specific vocabulary for the analysis

No programming knowledge is needed to edit these files. Open them in any text editor, add or remove keywords, and re-run the analysis.
