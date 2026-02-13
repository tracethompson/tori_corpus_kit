# docket-discourse v2.0

A Python analysis suite for analyzing ~6,950 FDA public comments from docket FDA-2015-D-3719 ("Human Cells, Tissues, and Cellular and Tissue-Based Products from Adipose Tissue: Regulatory Considerations").

## Features

- **API-based data collection** from regulations.gov
- **Word frequency analysis** with lemmatization via spaCy
- **Bigram and trigram extraction** (with and without stopwords)
- **MinHash/LSH duplicate detection** for identifying form letters vs. unique arguments
- **Temporal submission pattern analysis**
- **Citation extraction** (CFR, PHSA, guidance documents)
- **Publication-ready exports** (MLA 8 formatted quotes, 300dpi figures)

## Installation

### Prerequisites

- Python 3.9+
- regulations.gov API key ([Get one here](https://api.regulations.gov))

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

## Quick Start

### Run Complete Pipeline

```bash
python main.py --full
```

This runs all three phases:
1. **Data Collection**: Scrapes comments, searches related dockets, calculates baselines
2. **Analysis**: Corpus NLP (word freq, bigrams, trigrams), duplicate detection
3. **Export**: Generates publication-ready outputs

### Run Individual Phases

```bash
# Phase 1: Data Collection (requires API access)
python main.py --phase 1

# Phase 2: Analysis (requires Phase 1 data)
python main.py --phase 2

# Phase 3: Export (requires Phase 2 analysis)
python main.py --phase 3
```

### Run Individual Tools

```bash
# Data collection tools
python main.py --tool scraper         # Fetch comments from regulations.gov
python main.py --tool scraper --limit 100  # Test with 100 comments
python main.py --tool search          # Find related FDA dockets
python main.py --tool baseline        # Calculate baseline statistics

# Analysis tools
python main.py --tool corpus          # Word frequencies, bigrams, trigrams
python main.py --tool frames          # Rhetorical frame detection
python main.py --tool temporal        # Timeline and duplicate detection
python main.py --tool citations       # Citation extraction

# Export tools
python main.py --tool charts          # Generate visualizations
python main.py --tool export          # Publication formatting
```

## Project Structure

```
docket-discourse/
├── scrapers/
│   ├── regulations_scraper.py    # API scraper
│   ├── docket_search.py          # Related docket search
│   └── baseline_calculator.py    # Baseline statistics
├── analyzers/
│   ├── corpus_analyzer.py        # Word freq, bigrams, trigrams
│   ├── frame_detector.py         # Frame detection (opt-in)
│   └── temporal_mapper.py        # Timeline & duplicates
├── visualization/
│   ├── citation_extractor.py     # Citation extraction
│   └── chart_generator.py        # Visualization
├── utils/
│   ├── config.py                 # Central configuration
│   ├── data_loader.py            # Data loading utilities
│   └── export_formatter.py       # Publication export
├── data/
│   ├── raw/                      # Raw scraped data
│   ├── processed/                # Analysis outputs
│   └── outputs/                  # Publication-ready exports
├── tests/                        # pytest unit tests
├── main.py                       # CLI entry point
└── requirements.txt
```

## Output Files

### data/raw/
- `comments.json` - Full structured comment data
- `comments.csv` - Flattened CSV
- `comments_searchable_ALL.txt` - All comments as searchable text

### data/processed/
- `word_freq_with_stopwords.csv` / `word_freq_no_stopwords.csv`
- `bigrams_with_stopwords.csv` / `bigrams_no_stopwords.csv`
- `trigrams_with_stopwords.csv` / `trigrams_no_stopwords.csv`
- `corpus_summary.json` - Summary statistics
- `duplicate_comment_groups.csv`
- `unique_arguments_analysis.json`
- `citations_*.csv` - Extracted regulatory citations

### data/outputs/
- `figures/` - PNG (300dpi) and PDF visualizations
- `quotes/` - Thematic quote collections with MLA citations
- `methodology.md` - Generated methodology section

## Duplicate Detection

Near-duplicates are identified using MinHash/LSH:
- 128 permutations
- Word-level 3-shingles
- 0.9 similarity threshold

## Testing

```bash
pytest tests/
pytest tests/ --cov=.
```

## API Rate Limiting

The regulations.gov API has default limits of 1000 requests/hour. The scraper includes automatic rate limiting, checkpoint/resume, and retry on 429 errors.

## License

MIT License
