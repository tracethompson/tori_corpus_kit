# docket-discourse

A Python toolkit for collecting and analyzing FDA public comments from docket FDA-2015-D-3719 ("Human Cells, Tissues, and Cellular and Tissue-Based Products from Adipose Tissue: Regulatory Considerations").

**Dataset:** 6,959 comments collected via the regulations.gov API, with 39 PDF attachments.

## What This Tool Does

1. **Scrapes comments** from the regulations.gov API (with rate limiting and checkpoint/resume)
2. **Generates word frequencies** — the most common words across all comments
3. **Generates bigrams and trigrams** — the most common two- and three-word phrases
4. **Extracts regulatory citations** — references to CFR sections, PHSA, guidance documents
5. **Detects duplicate/form letter comments** using MinHash/LSH similarity
6. **Exports publication-ready outputs** — MLA 8 citations, 300dpi figures, methodology text

## Finding the Data

### Raw Comments

All in `data/raw/`:

| File | What it is |
|---|---|
| `comments_searchable_ALL.txt` | Every comment as readable text, separated by headers. Open this to search or browse comments. |
| `comments.json` | All 6,959 comments with full metadata (submitter, date, ID, word count, attachment info). |
| `comments.csv` | Same data as a spreadsheet. Open in Excel or Google Sheets. |
| `manual_attachments/` | 39 PDF files from 27 comments that included attached documents. Organized by comment ID. |
| `FDA-2015-D-3719_checkpoint.json` | Scraper checkpoint file (used for resume on interruption). |

### Analysis Results

All in `data/processed/`:

| File | What it is |
|---|---|
| `word_freq_no_stopwords.csv` | Top words by frequency, with common words ("the", "is") filtered out. |
| `word_freq_with_stopwords.csv` | Top words by frequency, keeping all words. |
| `bigrams_no_stopwords.csv` | Top two-word pairs, common words filtered out. |
| `bigrams_with_stopwords.csv` | Top two-word pairs, keeping all words. |
| `trigrams_no_stopwords.csv` | Top three-word phrases, common words filtered out. |
| `trigrams_with_stopwords.csv` | Top three-word phrases, keeping all words. |
| `corpus_summary.json` | Summary stats (total comments, total words, avg length). |
| `citations_all.csv` | Every regulatory citation found across all comments. |
| `citations_guidance.csv` | Citations to FDA guidance documents specifically. |
| `citations_technical_terms.csv` | Technical/regulatory term usage. |
| `citation_summary.json` | Citation count summary. |

### Publication Outputs

All in `data/outputs/`:

| File | What it is |
|---|---|
| `figures/` | Charts and visualizations (PNG at 300dpi and PDF). |

## Installation

### Prerequisites

- Python 3.9+
- regulations.gov API key ([get one here](https://api.regulations.gov))

### Setup

```bash
cd docket-discourse

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Download spaCy language model
python -m spacy download en_core_web_sm

# Set API key environment variable
export REGULATIONS_GOV_API_KEY="your-api-key-here"
```

### Verify Installation

```bash
python main.py --validate-api
```

## Usage

### Run the Full Pipeline

```bash
python main.py --full
```

This runs three phases in order:
1. **Data Collection** — scrapes comments, fetches attachments
2. **Analysis** — word frequencies, bigrams, trigrams
3. **Export** — generates publication-ready outputs

### Run Individual Phases

```bash
python main.py --phase 1    # Data collection (requires API key)
python main.py --phase 2    # Analysis (requires phase 1 data)
python main.py --phase 3    # Export (requires phase 2 results)
```

### Run a Single Tool

```bash
# Data collection
python main.py --tool scraper              # Fetch all comments
python main.py --tool scraper --limit 100  # Test with 100 comments
python main.py --tool search               # Find related FDA dockets
python main.py --tool baseline             # Calculate baseline statistics

# Analysis
python main.py --tool corpus      # Word frequencies, bigrams, trigrams
python main.py --tool temporal    # Timeline analysis and duplicate detection
python main.py --tool citations   # Extract regulatory citations
python main.py --tool frames      # Rhetorical frame detection (opt-in)

# Export
python main.py --tool charts     # Generate visualizations
python main.py --tool export     # Publication formatting (MLA 8 quotes, methodology)
```

## How the Analysis Works

### Word Frequencies
Each comment is tokenized using spaCy (`en_core_web_sm` model) and lemmatized (e.g., "regulations" becomes "regulation"). Words are counted across all 6,959 comments. Two versions are produced: one keeping all words, one filtering out stopwords (common words like "the", "and", "is").

### Bigrams and Trigrams
After tokenization, consecutive word pairs (bigrams) and triples (trigrams) are extracted. N-grams where every word is a stopword or 2 characters or fewer are filtered out in the "no stopwords" versions.

### Duplicate Detection
Near-duplicate comments (form letters) are identified using MinHash/LSH with 128 permutations, word-level 3-shingles, and a 0.9 similarity threshold.

## Project Structure

```
docket-discourse/
├── main.py                       CLI entry point
├── scrapers/
│   ├── regulations_scraper.py    API scraper with checkpoint/resume
│   ├── attachment_fetcher.py     PDF attachment downloader
│   ├── docket_search.py          Related docket search
│   └── baseline_calculator.py    Baseline statistics
├── analyzers/
│   ├── corpus_analyzer.py        Word freq, bigrams, trigrams
│   ├── temporal_mapper.py        Timeline and duplicate detection
│   └── frame_detector.py         Rhetorical frame detection (opt-in)
├── visualization/
│   ├── citation_extractor.py     Regulatory citation extraction
│   └── chart_generator.py        Chart generation
├── utils/
│   ├── config.py                 Central configuration
│   ├── data_loader.py            Data loading and saving
│   ├── comment_classifier.py     Comment classification (available, not active)
│   └── export_formatter.py       Publication export formatting
├── dictionaries/                 Keyword and term dictionaries
├── data/
│   ├── raw/                      Downloaded comments and attachments
│   ├── processed/                Analysis output CSVs and JSONs
│   └── outputs/                  Publication-ready figures
├── tests/                        pytest unit tests
└── requirements.txt
```

## Testing

```bash
pytest tests/
pytest tests/ --cov=.
```

## API Rate Limiting

The regulations.gov API allows 1,000 requests/hour. The scraper handles this automatically with built-in rate limiting (~3.6s delay between requests), checkpoint/resume every 100 comments, and retry on 429 errors. A full scrape of ~7,000 comments takes approximately 8 hours.

## License

MIT License
