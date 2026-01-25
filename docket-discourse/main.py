#!/usr/bin/env python3
"""
docket-discourse v2.0

FDA Public Comment Analysis Suite for docket FDA-2015-D-3719.
A 9-tool analysis pipeline for 6,950 public comments on HCTP regulations.

Usage:
    python main.py --phase 1      # Run data collection phase
    python main.py --phase 2      # Run analysis phase
    python main.py --tool scraper # Run specific tool
    python main.py --full         # Run complete pipeline
"""
import argparse
import logging
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from utils import config

logging.basicConfig(
    level=logging.INFO,
    format=config.LOG_FORMAT,
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(config.PROJECT_ROOT / "docket-discourse.log"),
    ]
)
logger = logging.getLogger(__name__)


def run_phase_1():
    """Phase 1: Data Collection (Tools 1-3)."""
    logger.info("=" * 60)
    logger.info("PHASE 1: DATA COLLECTION")
    logger.info("=" * 60)

    # Tool 1: Regulations Scraper
    logger.info("\n[Tool 1] Running Regulations Scraper...")
    try:
        from scrapers.regulations_scraper import RegulationsScraper
        scraper = RegulationsScraper()
        comments = scraper.scrape_docket()
        scraper.export_searchable_text(comments)
        scraper.export_csv(comments)
        logger.info(f"Scraped {len(comments)} comments")
    except Exception as e:
        logger.error(f"Scraper error: {e}")
        raise

    # Tool 2: Docket Search
    logger.info("\n[Tool 2] Searching for related dockets...")
    try:
        from scrapers.docket_search import DocketSearcher
        searcher = DocketSearcher()
        results = searcher.search_related_dockets()
        searcher.export_search_results(results)
        logger.info("Related docket search complete")
    except Exception as e:
        logger.error(f"Docket search error: {e}")

    # Tool 3: Baseline Calculator
    logger.info("\n[Tool 3] Calculating baseline statistics...")
    try:
        from scrapers.baseline_calculator import BaselineCalculator
        calculator = BaselineCalculator()
        dockets, stats = calculator.run_full_analysis()
        logger.info(f"Baseline calculated from {len(dockets)} dockets")
    except Exception as e:
        logger.error(f"Baseline calculator error: {e}")


def run_phase_2():
    """Phase 2: Analysis (Tools 4-8)."""
    logger.info("=" * 60)
    logger.info("PHASE 2: ANALYSIS")
    logger.info("=" * 60)

    # Load comments
    from utils.data_loader import DataLoader
    loader = DataLoader()
    comments = loader.load_comments_json()

    if not comments:
        logger.error("No comments found. Run Phase 1 first.")
        return

    logger.info(f"Loaded {len(comments)} comments for analysis")

    # Tool 4: Corpus Analyzer
    logger.info("\n[Tool 4] Running Corpus Analyzer...")
    try:
        from analyzers.corpus_analyzer import CorpusAnalyzer
        analyzer = CorpusAnalyzer()
        analyzer.run_three_track_analysis(comments)
        analyzer.generate_summary_report(comments)
        logger.info("Corpus analysis complete")
    except Exception as e:
        logger.error(f"Corpus analyzer error: {e}")

    # Tool 5: Frame Detector
    logger.info("\n[Tool 5] Running Frame Detector...")
    try:
        from analyzers.frame_detector import FrameDetector
        detector = FrameDetector()
        detector.analyze_corpus(comments)
        logger.info("Frame detection complete")
    except Exception as e:
        logger.error(f"Frame detector error: {e}")

    # Tool 6: Stakeholder Classifier
    logger.info("\n[Tool 6] Running Stakeholder Classifier...")
    try:
        from analyzers.stakeholder_classifier import StakeholderClassifier
        classifier = StakeholderClassifier()
        classifier.classify_corpus(comments)
        logger.info("Stakeholder classification complete")
    except Exception as e:
        logger.error(f"Stakeholder classifier error: {e}")

    # Tool 7: Temporal Mapper
    logger.info("\n[Tool 7] Running Temporal Mapper...")
    try:
        from analyzers.temporal_mapper import TemporalMapper
        mapper = TemporalMapper()
        mapper.run_full_analysis(comments)
        logger.info("Temporal analysis complete")
    except Exception as e:
        logger.error(f"Temporal mapper error: {e}")

    # Tool 8: Citation Extractor
    logger.info("\n[Tool 8] Running Citation Extractor...")
    try:
        from visualization.citation_extractor import CitationExtractor
        extractor = CitationExtractor()
        extractor.analyze_corpus(comments)
        logger.info("Citation extraction complete")
    except Exception as e:
        logger.error(f"Citation extractor error: {e}")


def run_phase_3():
    """Phase 3: Visualization and Export (Tool 9)."""
    logger.info("=" * 60)
    logger.info("PHASE 3: EXPORT & VISUALIZATION")
    logger.info("=" * 60)

    # Load comments
    from utils.data_loader import DataLoader
    loader = DataLoader()
    comments = loader.load_comments_json()

    # Generate charts
    logger.info("\n[Charts] Generating visualizations...")
    try:
        from visualization.chart_generator import ChartGenerator
        generator = ChartGenerator()
        generator.generate_all_charts(comments)
        logger.info("Chart generation complete")
    except Exception as e:
        logger.error(f"Chart generator error: {e}")

    # Tool 9: Export Formatter
    logger.info("\n[Tool 9] Running Export Formatter...")
    try:
        from utils.export_formatter import ExportFormatter
        formatter = ExportFormatter()
        formatter.export_full_report(comments)
        logger.info("Export complete")
    except Exception as e:
        logger.error(f"Export formatter error: {e}")


def run_tool(tool_name: str, **kwargs):
    """Run a specific tool."""
    tools = {
        "scraper": run_scraper,
        "search": run_search,
        "baseline": run_baseline,
        "attachments": run_attachment_fetcher,
        "corpus": run_corpus_analyzer,
        "frames": run_frame_detector,
        "stakeholder": run_stakeholder_classifier,
        "temporal": run_temporal_mapper,
        "citations": run_citation_extractor,
        "charts": run_chart_generator,
        "export": run_export_formatter,
    }

    if tool_name not in tools:
        logger.error(f"Unknown tool: {tool_name}")
        logger.info(f"Available tools: {', '.join(tools.keys())}")
        return

    tools[tool_name](**kwargs)


def run_scraper(limit: int = None, **kwargs):
    """Run regulations scraper."""
    from scrapers.regulations_scraper import RegulationsScraper
    scraper = RegulationsScraper()
    comments = scraper.scrape_docket(limit=limit)
    scraper.export_searchable_text(comments)
    scraper.export_csv(comments)


def run_search(**kwargs):
    """Run docket search."""
    from scrapers.docket_search import DocketSearcher
    searcher = DocketSearcher()
    results = searcher.search_related_dockets()
    searcher.export_search_results(results)


def run_baseline(**kwargs):
    """Run baseline calculator."""
    from scrapers.baseline_calculator import BaselineCalculator
    calculator = BaselineCalculator()
    calculator.run_full_analysis()


def run_corpus_analyzer(**kwargs):
    """Run corpus analyzer."""
    from analyzers.corpus_analyzer import CorpusAnalyzer
    from utils.data_loader import DataLoader
    loader = DataLoader()
    comments = loader.load_comments_json()
    analyzer = CorpusAnalyzer()
    analyzer.run_three_track_analysis(comments)


def run_frame_detector(**kwargs):
    """Run frame detector."""
    from analyzers.frame_detector import FrameDetector
    from utils.data_loader import DataLoader
    loader = DataLoader()
    comments = loader.load_comments_json()
    detector = FrameDetector()
    detector.analyze_corpus(comments)


def run_stakeholder_classifier(**kwargs):
    """Run stakeholder classifier."""
    from analyzers.stakeholder_classifier import StakeholderClassifier
    from utils.data_loader import DataLoader
    loader = DataLoader()
    comments = loader.load_comments_json()
    classifier = StakeholderClassifier()
    classifier.classify_corpus(comments)


def run_temporal_mapper(**kwargs):
    """Run temporal mapper."""
    from analyzers.temporal_mapper import TemporalMapper
    from utils.data_loader import DataLoader
    loader = DataLoader()
    comments = loader.load_comments_json()
    mapper = TemporalMapper()
    mapper.run_full_analysis(comments)


def run_citation_extractor(**kwargs):
    """Run citation extractor."""
    from visualization.citation_extractor import CitationExtractor
    from utils.data_loader import DataLoader
    loader = DataLoader()
    comments = loader.load_comments_json()
    extractor = CitationExtractor()
    extractor.analyze_corpus(comments)


def run_chart_generator(**kwargs):
    """Run chart generator."""
    from visualization.chart_generator import ChartGenerator
    from utils.data_loader import DataLoader
    loader = DataLoader()
    comments = loader.load_comments_json()
    generator = ChartGenerator()
    generator.generate_all_charts(comments)


def run_export_formatter(**kwargs):
    """Run export formatter."""
    from utils.export_formatter import ExportFormatter
    from utils.data_loader import DataLoader
    loader = DataLoader()
    comments = loader.load_comments_json()
    formatter = ExportFormatter()
    formatter.export_full_report(comments)


def run_attachment_fetcher(**kwargs):
    """Run manual attachment fetcher."""
    from scrapers.attachment_fetcher import AttachmentFetcher
    fetcher = AttachmentFetcher()
    fetcher.run()


def run_full_pipeline():
    """Run complete analysis pipeline."""
    logger.info("=" * 60)
    logger.info("DOCKET-DISCOURSE v2.0 - FULL PIPELINE")
    logger.info("=" * 60)
    logger.info(f"Target docket: {config.DOCKET_ID}")
    logger.info(f"Expected comments: {config.EXPECTED_COMMENT_COUNT}")
    logger.info("=" * 60)

    config.ensure_directories()

    run_phase_1()
    run_phase_2()
    run_phase_3()

    logger.info("\n" + "=" * 60)
    logger.info("PIPELINE COMPLETE")
    logger.info("=" * 60)
    logger.info(f"Raw data: {config.RAW_DIR}")
    logger.info(f"Processed data: {config.PROCESSED_DIR}")
    logger.info(f"Outputs: {config.OUTPUTS_DIR}")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="docket-discourse: FDA Public Comment Analysis Suite",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    python main.py --full                 # Run complete pipeline
    python main.py --phase 1              # Run data collection
    python main.py --phase 2              # Run analysis
    python main.py --phase 3              # Run export
    python main.py --tool scraper         # Run specific tool
    python main.py --tool scraper --limit 100  # Test with 100 comments
    python main.py --filter personal      # Filter to personal narratives

Tools:
    scraper     - Regulations.gov API scraper
    search      - Related docket search
    baseline    - Baseline statistics calculator
    attachments - Attempt to fetch missing attachments from downloads site
    corpus      - Corpus NLP analyzer
    frames      - Rhetorical frame detector
    stakeholder - Stakeholder classifier
    temporal    - Temporal/duplicate analysis
    citations   - Citation extractor
    charts      - Chart generator
    export      - Publication formatter
        """,
    )

    parser.add_argument(
        "--phase",
        type=int,
        choices=[1, 2, 3],
        help="Run specific phase (1=collection, 2=analysis, 3=export)",
    )
    parser.add_argument(
        "--tool",
        choices=[
            "scraper", "search", "baseline", "attachments",
            "corpus", "frames", "stakeholder", "temporal",
            "citations", "charts", "export",
        ],
        help="Run specific tool",
    )
    parser.add_argument(
        "--full",
        action="store_true",
        help="Run complete pipeline",
    )
    parser.add_argument(
        "--limit",
        type=int,
        help="Limit number of comments (for testing)",
    )
    parser.add_argument(
        "--filter",
        choices=["personal", "technical", "organizational"],
        help="Filter to specific comment type",
    )
    parser.add_argument(
        "--validate-api",
        action="store_true",
        help="Validate API key and exit",
    )

    args = parser.parse_args()

    # Validate API key if requested
    if args.validate_api:
        try:
            config.validate_api_key()
            print("API key is configured correctly")
        except ValueError as e:
            print(f"API key error: {e}")
            sys.exit(1)
        return

    # Ensure directories exist
    config.ensure_directories()

    # Run based on arguments
    if args.full:
        run_full_pipeline()
    elif args.phase:
        if args.phase == 1:
            run_phase_1()
        elif args.phase == 2:
            run_phase_2()
        elif args.phase == 3:
            run_phase_3()
    elif args.tool:
        run_tool(args.tool, limit=args.limit)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
