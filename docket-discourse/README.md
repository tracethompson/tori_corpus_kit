# docket-discourse v2.0

A 9-tool Python analysis suite for analyzing 6,950 FDA public comments from docket FDA-2015-D-3719 ("Human Cells, Tissues, and Cellular and Tissue-Based Products from Adipose Tissue: Regulatory Considerations").

## Features

- **API-based data collection** from regulations.gov
- **Automatic comment classification** (Personal Narrative / Technical Document / Organizational)
- **MinHash/LSH duplicate detection** for identifying form letters vs. unique arguments
- **Four-frame rhetorical analysis** (Body/Self, Product/Drug, Treatment/Therapy, Economic/Access)
- **Multi-signal stakeholder classification** with confidence scoring
- **Temporal submission pattern analysis**
- **Citation extraction** (CFR, PHSA, guidance documents)
- **Publication-ready exports** (MLA 8 formatted tables, 300dpi figures)

## Installation

### Prerequisites

- Python 3.9+
- regulations.gov API key ([Get one here](https://api.regulations.gov))

### Setup

```bash
# Clone the repository
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
2. **Analysis**: Corpus NLP, frame detection, stakeholder classification, duplicate detection
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
python main.py --tool corpus          # NLP corpus analysis
python main.py --tool frames          # Rhetorical frame detection
python main.py --tool stakeholder     # Stakeholder classification
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
│   ├── regulations_scraper.py    # Tool 1: API scraper
│   ├── docket_search.py          # Tool 2: Related docket search
│   └── baseline_calculator.py    # Tool 3: Baseline statistics
├── analyzers/
│   ├── corpus_analyzer.py        # Tool 4: NLP analysis
│   ├── frame_detector.py         # Tool 5: Frame detection
│   ├── stakeholder_classifier.py # Tool 6: Stakeholder classification
│   └── temporal_mapper.py        # Tool 7: Timeline & duplicates
├── visualization/
│   ├── citation_extractor.py     # Tool 8: Citation extraction
│   └── chart_generator.py        # Supporting visualization
├── utils/
│   ├── config.py                 # Central configuration
│   ├── data_loader.py            # Data loading utilities
│   ├── comment_classifier.py     # Classification logic
│   └── export_formatter.py       # Tool 9: Publication export
├── dictionaries/
│   ├── technical_terms.json      # Technical vocabulary
│   └── stakeholder_keywords.json # Stakeholder classification keywords
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
- `comments.csv` - Flattened CSV with classification columns
- `comments_searchable_ALL.txt` - All comments as searchable text
- `comments_searchable_personal_narratives.txt`
- `comments_searchable_technical_documents.txt`
- `comments_searchable_organizational.txt`

### data/processed/
- `word_freq_*.csv` - Word frequency analysis (18 files)
- `possessive_analysis.json` - Possessive language patterns
- `four_frame_distribution.json` - Frame analysis results
- `stakeholder_classifications_high_confidence.csv`
- `duplicate_comment_groups.csv`
- `unique_arguments_analysis.json`
- `citations_*.csv` - Extracted regulatory citations

### data/outputs/
- `tables/` - DOCX and LaTeX formatted tables
- `figures/` - PNG (300dpi) and PDF visualizations
- `quotes/` - Thematic quote collections with MLA citations
- `methodology.md` - Generated methodology section

## Customizing the Analysis

### Editing Dictionaries

The analysis uses editable JSON dictionaries:

**dictionaries/stakeholder_keywords.json**
Add or modify keywords to refine stakeholder classification:
```json
{
  "stakeholder_categories": {
    "patient": {
      "keywords": ["as a patient", "my treatment", "my condition"],
      "possessive_weight": 2.0
    }
  }
}
```

**dictionaries/technical_terms.json**
Add domain-specific technical vocabulary:
```json
{
  "technical_terms": {
    "hctp_terminology": ["HCT/P", "stem cells", "regenerative"]
  }
}
```

### Adjusting Thresholds

Edit `utils/config.py` to adjust:
- Classification thresholds
- MinHash similarity threshold (default: 0.9)
- Rate limiting delays
- Output formats

## Testing

```bash
# Run all tests
pytest tests/

# Run with coverage
pytest tests/ --cov=.

# Run specific test file
pytest tests/test_classifier.py -v
```

## API Rate Limiting

The regulations.gov API has default limits of 1000 requests/hour. With ~6,950 comments plus detail fetches:
- Estimated total requests: ~14,000
- Estimated time at default rate: ~14 hours

The scraper includes:
- Automatic rate limiting (configurable delay)
- Checkpoint/resume functionality
- Automatic retry on 429 errors

To request a higher rate limit, contact regulations.gov support.

## Methodological Notes

### Comment Classification
Comments are classified using a multi-signal approach:
- **Personal Narratives**: High possessive language ("my", "our"), first-person health accounts
- **Technical Documents**: High regulatory citation density, legal/procedural language
- **Organizational**: Formal submission language ("on behalf of", "our organization")

### Duplicate Detection
Near-duplicates are identified using MinHash/LSH:
- 128 permutations
- Word-level 3-shingles
- 0.9 similarity threshold

### Stakeholder Classification
Confidence levels:
- **High**: Multiple strong signals, credential matches
- **Medium**: Some signals present
- **Low**: Weak or ambiguous signals (flagged for manual review)

### PDF Handling
PDFs are extracted with PyPDF2 and **flagged for manual review** due to potential extraction errors.

## Verification Steps

After running the pipeline:

1. **Sample Check**: Manually verify 20-50 comment classifications
2. **Duplicate Validation**: Review `duplicate_group_samples.csv` for accuracy
3. **Stakeholder Review**: Check `stakeholder_manual_review.csv` for edge cases
4. **Citation Spot-Check**: Verify extracted citations against original PDFs

## Citation

If using this tool for research, please cite:
```
FDA Public Comment Analysis Suite (docket-discourse v2.0)
Docket: FDA-2015-D-3719
```

## License

MIT License

## Acknowledgments

- Data source: [regulations.gov](https://regulations.gov)
- NLP: [spaCy](https://spacy.io/)
- Duplicate detection: [datasketch](https://github.com/ekzhu/datasketch)
