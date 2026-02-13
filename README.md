# Tori Corpus Kit

An analysis toolkit for studying FDA public comments on docket **FDA-2015-D-3719** — the regulatory proposal on *Human Cells, Tissues, and Cellular and Tissue-Based Products from Adipose Tissue*.

This toolkit downloaded and analyzed **6,959 public comments** submitted to the FDA, producing searchable text files, word frequencies, bigrams, trigrams, and publication-ready outputs.

---

## Where to Find Things

### Reading Comments

| What you want | Where to look |
|---|---|
| All comments as plain text (searchable) | [`data/raw/comments_searchable_ALL.txt`](docket-discourse/data/raw/comments_searchable_ALL.txt) |
| Full structured data (JSON) | [`data/raw/comments.json`](docket-discourse/data/raw/comments.json) |
| Spreadsheet format (CSV) | [`data/raw/comments.csv`](docket-discourse/data/raw/comments.csv) |
| PDF attachments (39 files) | [`data/raw/manual_attachments/`](docket-discourse/data/raw/manual_attachments/) |

**Tip:** The searchable text file is the easiest way to read through comments. Each comment is separated by a header with the submitter name, date, and comment ID. Use Ctrl+F / Cmd+F to search for keywords.

### Word Frequencies and N-Grams

| What you want | Where to look |
|---|---|
| Most common words (with stopwords) | [`data/processed/word_freq_with_stopwords.csv`](docket-discourse/data/processed/word_freq_with_stopwords.csv) |
| Most common words (no stopwords) | [`data/processed/word_freq_no_stopwords.csv`](docket-discourse/data/processed/word_freq_no_stopwords.csv) |
| Bigrams — two-word pairs (with stopwords) | [`data/processed/bigrams_with_stopwords.csv`](docket-discourse/data/processed/bigrams_with_stopwords.csv) |
| Bigrams — two-word pairs (no stopwords) | [`data/processed/bigrams_no_stopwords.csv`](docket-discourse/data/processed/bigrams_no_stopwords.csv) |
| Trigrams — three-word phrases (with stopwords) | [`data/processed/trigrams_with_stopwords.csv`](docket-discourse/data/processed/trigrams_with_stopwords.csv) |
| Trigrams — three-word phrases (no stopwords) | [`data/processed/trigrams_no_stopwords.csv`](docket-discourse/data/processed/trigrams_no_stopwords.csv) |

**With vs. without stopwords:** Stopwords are common words like "the", "is", "and". The "no stopwords" versions filter these out so you can see the meaningful content words. The "with stopwords" versions keep everything, which is useful for seeing natural phrasing.

### Other Analysis Files

| What you want | Where to look |
|---|---|
| Corpus summary statistics | [`data/processed/corpus_summary.json`](docket-discourse/data/processed/corpus_summary.json) |
| Regulatory citation extraction | [`data/processed/citations_all.csv`](docket-discourse/data/processed/citations_all.csv) |
| Citation summary | [`data/processed/citation_summary.json`](docket-discourse/data/processed/citation_summary.json) |
| Charts and figures | [`data/outputs/figures/`](docket-discourse/data/outputs/figures/) |

---

## Directory Overview

```
tori_corpus_kit/
└── docket-discourse/
    ├── main.py                    Run this to start any tool
    ├── data/
    │   ├── raw/
    │   │   ├── comments.json              All 6,959 comments (structured)
    │   │   ├── comments.csv               All comments (spreadsheet)
    │   │   ├── comments_searchable_ALL.txt All comments (readable text)
    │   │   └── manual_attachments/        39 PDF attachments
    │   ├── processed/
    │   │   ├── word_freq_*.csv            Word frequency counts
    │   │   ├── bigrams_*.csv              Two-word pair counts
    │   │   ├── trigrams_*.csv             Three-word phrase counts
    │   │   ├── citations_*.csv            Regulatory citation data
    │   │   └── corpus_summary.json        Summary statistics
    │   └── outputs/
    │       └── figures/                   Charts and visualizations
    ├── scrapers/                  Downloads comments from regulations.gov
    ├── analyzers/                 NLP analysis (word freq, n-grams)
    ├── visualization/             Charts and citation extraction
    ├── utils/                     Configuration and helpers
    └── tests/                     Automated tests
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
python main.py --tool corpus          # Word frequencies, bigrams, trigrams
python main.py --tool export          # Generate publication files
```

See [`docket-discourse/README.md`](docket-discourse/README.md) for the full list of tools and options.
