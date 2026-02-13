"""
Tool 4: Corpus Analyzer

Perform NLP analysis on FDA public comments corpus.
Generates word frequencies, n-grams, and possessive language analysis
for three parallel tracks: All, Personal Narratives, Technical Documents.
"""
import logging
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from collections import Counter
import re
import json

import pandas as pd
import numpy as np

try:
    import spacy
    SPACY_AVAILABLE = True
except ImportError:
    SPACY_AVAILABLE = False

try:
    import nltk
    from nltk.corpus import stopwords
    from nltk.util import ngrams
    NLTK_AVAILABLE = True
except ImportError:
    NLTK_AVAILABLE = False

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from utils import config
from utils.data_loader import DataLoader

logging.basicConfig(level=logging.INFO, format=config.LOG_FORMAT)
logger = logging.getLogger(__name__)


class CorpusAnalyzer:
    """Analyze FDA comment corpus with NLP techniques."""

    def __init__(self):
        """Initialize analyzer with NLP models."""
        self.data_loader = DataLoader()

        # Load spaCy model
        self.nlp = None
        if SPACY_AVAILABLE:
            try:
                self.nlp = spacy.load("en_core_web_sm")
                logger.info("Loaded spaCy model")
            except OSError:
                logger.warning("spaCy model not found. Run: python -m spacy download en_core_web_sm")

        # Load NLTK stopwords
        self.stopwords = set()
        if NLTK_AVAILABLE:
            try:
                self.stopwords = set(stopwords.words("english"))
            except LookupError:
                nltk.download("stopwords", quiet=True)
                self.stopwords = set(stopwords.words("english"))

        # Add domain-specific stopwords
        self.domain_stopwords = {
            "fda", "comment", "guidance", "draft", "docket",
            "submitted", "public", "federal", "register",
        }
        self.stopwords.update(self.domain_stopwords)

    def preprocess_text(self, text: str) -> Dict:
        """
        Preprocess text with tokenization, lemmatization, and POS tagging.

        Args:
            text: Raw text

        Returns:
            Dict with processed tokens and metadata
        """
        if not text or not self.nlp:
            return {
                "tokens": [],
                "lemmas": [],
                "pos_tags": [],
                "noun_phrases": [],
            }

        # Process with spaCy
        doc = self.nlp(text[:100000])  # Limit for very long documents

        tokens = []
        lemmas = []
        pos_tags = []

        for token in doc:
            if not token.is_punct and not token.is_space:
                tokens.append(token.text.lower())
                lemmas.append(token.lemma_.lower())
                pos_tags.append((token.text, token.pos_))

        # Extract noun phrases
        noun_phrases = [chunk.text.lower() for chunk in doc.noun_chunks]

        return {
            "tokens": tokens,
            "lemmas": lemmas,
            "pos_tags": pos_tags,
            "noun_phrases": noun_phrases,
        }

    def calculate_word_frequencies(
        self,
        texts: List[str],
        use_lemmas: bool = True,
        remove_stopwords: bool = True,
        top_n: int = 500,
    ) -> List[Tuple[str, int]]:
        """
        Calculate word frequencies across corpus.

        Args:
            texts: List of text strings
            use_lemmas: Use lemmatized forms
            remove_stopwords: Filter out stopwords
            top_n: Number of top words to return

        Returns:
            List of (word, count) tuples
        """
        word_counts = Counter()

        for text in texts:
            processed = self.preprocess_text(text)
            words = processed["lemmas"] if use_lemmas else processed["tokens"]

            if remove_stopwords:
                words = [w for w in words if w not in self.stopwords and len(w) > 2]

            word_counts.update(words)

        return word_counts.most_common(top_n)

    def calculate_ngrams(
        self,
        texts: List[str],
        n: int = 2,
        remove_stopwords: bool = True,
        top_n: int = 200,
    ) -> List[Tuple[str, int]]:
        """
        Calculate n-gram frequencies.

        Args:
            texts: List of text strings
            n: N-gram size (2 for bigrams, 3 for trigrams)
            remove_stopwords: Filter n-grams containing stopwords
            top_n: Number of top n-grams to return

        Returns:
            List of (ngram_string, count) tuples
        """
        ngram_counts = Counter()

        for text in texts:
            processed = self.preprocess_text(text)
            tokens = processed["lemmas"]

            # Generate n-grams
            text_ngrams = list(ngrams(tokens, n)) if NLTK_AVAILABLE else self._simple_ngrams(tokens, n)

            for gram in text_ngrams:
                # Filter based on stopwords
                if remove_stopwords:
                    if all(w in self.stopwords or len(w) <= 2 for w in gram):
                        continue

                ngram_str = " ".join(gram)
                ngram_counts[ngram_str] += 1

        return ngram_counts.most_common(top_n)

    def _simple_ngrams(self, tokens: List[str], n: int) -> List[Tuple]:
        """Simple n-gram generation without NLTK."""
        return [tuple(tokens[i:i+n]) for i in range(len(tokens) - n + 1)]

    def run_analysis(
        self,
        comments: Optional[List[Dict]] = None,
        output_dir: Optional[Path] = None,
    ) -> Dict[str, Path]:
        """
        Run word frequency and n-gram analysis on the full corpus.

        Args:
            comments: List of comment dicts (or load from file)
            output_dir: Output directory

        Returns:
            Dict of output file paths
        """
        if comments is None:
            comments = self.data_loader.load_comments_json()

        if output_dir is None:
            output_dir = config.PROCESSED_DIR

        config.ensure_directories()

        texts = [c.get("full_text", c.get("comment_text", "")) for c in comments]
        output_files = {}

        if not texts:
            logger.warning("No texts to analyze")
            return output_files

        logger.info(f"Analyzing {len(texts)} documents")

        # Word frequencies (with and without stopwords)
        for with_sw, suffix in [(True, "with_stopwords"), (False, "no_stopwords")]:
            freq = self.calculate_word_frequencies(
                texts,
                remove_stopwords=not with_sw,
            )
            df = pd.DataFrame(freq, columns=["word", "count"])
            path = output_dir / f"word_freq_{suffix}.csv"
            df.to_csv(path, index=False)
            output_files[f"word_freq_{suffix}"] = path

        # Bigrams
        for with_sw, suffix in [(True, "with_stopwords"), (False, "no_stopwords")]:
            bigrams = self.calculate_ngrams(
                texts, n=2,
                remove_stopwords=not with_sw,
            )
            df = pd.DataFrame(bigrams, columns=["bigram", "count"])
            path = output_dir / f"bigrams_{suffix}.csv"
            df.to_csv(path, index=False)
            output_files[f"bigrams_{suffix}"] = path

        # Trigrams
        for with_sw, suffix in [(True, "with_stopwords"), (False, "no_stopwords")]:
            trigrams = self.calculate_ngrams(
                texts, n=3,
                remove_stopwords=not with_sw,
            )
            df = pd.DataFrame(trigrams, columns=["trigram", "count"])
            path = output_dir / f"trigrams_{suffix}.csv"
            df.to_csv(path, index=False)
            output_files[f"trigrams_{suffix}"] = path

        logger.info(f"Analysis complete. Generated {len(output_files)} output files.")
        return output_files

    def generate_summary_report(
        self,
        comments: Optional[List[Dict]] = None,
        output_path: Optional[Path] = None,
    ) -> Dict:
        """
        Generate summary statistics report.

        Args:
            comments: List of comments
            output_path: Output file path

        Returns:
            Summary statistics dict
        """
        if comments is None:
            comments = self.data_loader.load_comments_json()

        if output_path is None:
            output_path = config.PROCESSED_DIR / "corpus_summary.json"

        word_counts = [c.get("word_count", 0) for c in comments]

        summary = {
            "total_comments": len(comments),
            "total_words": sum(word_counts),
            "avg_words_per_comment": np.mean(word_counts) if word_counts else 0,
            "median_words": np.median(word_counts) if word_counts else 0,
        }

        self.data_loader.save_json(summary, output_path)
        return summary


def main():
    """Main entry point for corpus analyzer."""
    import argparse

    parser = argparse.ArgumentParser(description="Analyze FDA comment corpus")
    parser.add_argument("--input", help="Input JSON file path")
    parser.add_argument("--output-dir", help="Output directory")
    parser.add_argument("--summary-only", action="store_true", help="Only generate summary")
    args = parser.parse_args()

    analyzer = CorpusAnalyzer()

    input_path = Path(args.input) if args.input else None
    output_dir = Path(args.output_dir) if args.output_dir else None

    comments = analyzer.data_loader.load_comments_json(input_path)

    if not comments:
        logger.error("No comments found to analyze")
        return

    if args.summary_only:
        summary = analyzer.generate_summary_report(comments)
        print(json.dumps(summary, indent=2))
    else:
        output_files = analyzer.run_analysis(comments, output_dir)
        print(f"\nGenerated {len(output_files)} output files:")
        for name, path in output_files.items():
            print(f"  - {name}: {path}")


if __name__ == "__main__":
    main()
