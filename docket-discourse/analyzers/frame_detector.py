"""
Tool 5: Frame Detector

Detect rhetorical framing in FDA public comments.
Four primary frames: Body/Self, Product/Drug, Treatment/Therapy, Economic/Access.
"""
import logging
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from collections import Counter, defaultdict
import re
import json

import pandas as pd

try:
    import spacy
    SPACY_AVAILABLE = True
except ImportError:
    SPACY_AVAILABLE = False

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from utils import config
from utils.data_loader import DataLoader
from utils.comment_classifier import CommentClassifier

logging.basicConfig(level=logging.INFO, format=config.LOG_FORMAT)
logger = logging.getLogger(__name__)


class FrameDetector:
    """Detect rhetorical framing patterns in FDA comments."""

    def __init__(self):
        """Initialize frame detector."""
        self.data_loader = DataLoader()
        self.classifier = CommentClassifier()
        self.frames = config.FRAME_CATEGORIES

        # Load spaCy for noun phrase extraction
        self.nlp = None
        if SPACY_AVAILABLE:
            try:
                self.nlp = spacy.load("en_core_web_sm")
            except OSError:
                logger.warning("spaCy model not found")

        # Extended frame indicators for discovery mode
        self.extended_indicators = self._build_extended_indicators()

    def _build_extended_indicators(self) -> Dict[str, List[str]]:
        """Build extended indicator lists for each frame."""
        extended = {}

        for frame_id, frame_data in self.frames.items():
            base = frame_data["indicators"]

            # Add pattern variations
            variations = []
            for indicator in base:
                # Add possessive variations
                if not indicator.startswith("my "):
                    variations.append(f"my {indicator}")
                if not indicator.startswith("our "):
                    variations.append(f"our {indicator}")

            extended[frame_id] = base + variations

        return extended

    def detect_frames(self, text: str) -> Dict[str, Dict]:
        """
        Detect all frame types present in text.

        Args:
            text: Input text

        Returns:
            Dict with frame detection results
        """
        if not text:
            return {
                frame_id: {"present": False, "score": 0, "matches": []}
                for frame_id in self.frames
            }

        text_lower = text.lower()
        results = {}

        for frame_id, frame_data in self.frames.items():
            indicators = self.extended_indicators[frame_id]
            matches = []

            for indicator in indicators:
                count = text_lower.count(indicator)
                if count > 0:
                    matches.append({"indicator": indicator, "count": count})

            score = sum(m["count"] for m in matches)
            results[frame_id] = {
                "present": score > 0,
                "score": score,
                "matches": matches,
                "frame_name": frame_data["name"],
            }

        return results

    def extract_noun_phrases_by_frame(
        self,
        text: str,
        frame_id: str,
    ) -> List[Dict]:
        """
        Extract noun phrases associated with a specific frame.

        Args:
            text: Input text
            frame_id: Frame to analyze

        Returns:
            List of noun phrase contexts
        """
        if not self.nlp or not text:
            return []

        doc = self.nlp(text[:50000])  # Limit for long docs
        phrases = []

        frame_indicators = self.extended_indicators.get(frame_id, [])

        for chunk in doc.noun_chunks:
            chunk_lower = chunk.text.lower()

            # Check if noun phrase relates to frame
            for indicator in frame_indicators:
                if indicator in chunk_lower or chunk_lower in indicator:
                    phrases.append({
                        "phrase": chunk.text,
                        "root": chunk.root.text,
                        "indicator_match": indicator,
                        "start": chunk.start_char,
                        "end": chunk.end_char,
                    })
                    break

        return phrases

    def analyze_possessive_frames(
        self,
        text: str,
    ) -> Dict[str, List[Dict]]:
        """
        Categorize possessive constructions by frame.

        Args:
            text: Input text

        Returns:
            Dict mapping frames to possessive contexts
        """
        contexts = self.classifier.extract_possessive_contexts(text)

        frame_possessives = defaultdict(list)

        for ctx in contexts:
            # Determine which frame this possessive relates to
            context_lower = ctx["context"].lower()

            for frame_id, indicators in self.extended_indicators.items():
                for indicator in indicators:
                    if indicator in context_lower:
                        frame_possessives[frame_id].append({
                            "possessive": ctx["possessive"],
                            "context": ctx["context"],
                            "indicator": indicator,
                            "category": ctx["category"],
                        })
                        break

        return dict(frame_possessives)

    def run_discovery_mode(
        self,
        comments: List[Dict],
        sample_size: int = 100,
    ) -> Dict:
        """
        Discovery mode: find new potential frame indicators.

        Analyzes a sample to discover patterns not in the predefined lists.

        Args:
            comments: List of comment dicts
            sample_size: Number of comments to sample

        Returns:
            Discovery results with suggested new indicators
        """
        if not self.nlp:
            logger.warning("spaCy required for discovery mode")
            return {}

        # Sample comments
        import random
        sample = random.sample(comments, min(sample_size, len(comments)))

        # Collect all noun phrases
        all_phrases = Counter()
        possessive_phrases = Counter()

        for comment in sample:
            text = comment.get("full_text", comment.get("comment_text", ""))
            if not text:
                continue

            doc = self.nlp(text[:50000])

            for chunk in doc.noun_chunks:
                phrase = chunk.text.lower().strip()
                if len(phrase) > 3:
                    all_phrases[phrase] += 1

                    # Track possessive noun phrases
                    if phrase.startswith(("my ", "our ", "mine ", "ours ")):
                        possessive_phrases[phrase] += 1

        # Filter to frequent, uncategorized phrases
        discoveries = {
            "frequent_noun_phrases": [
                {"phrase": p, "count": c}
                for p, c in all_phrases.most_common(100)
                if c >= 3
            ],
            "possessive_phrases": [
                {"phrase": p, "count": c}
                for p, c in possessive_phrases.most_common(50)
            ],
            "uncategorized": [],
        }

        # Find phrases not matching existing indicators
        all_indicators = set()
        for indicators in self.extended_indicators.values():
            all_indicators.update(indicators)

        for phrase, count in all_phrases.most_common(200):
            if count >= 3 and not any(ind in phrase or phrase in ind for ind in all_indicators):
                # Check if potentially relevant
                relevant_keywords = [
                    "cell", "tissue", "body", "treatment", "therapy",
                    "drug", "product", "cost", "access", "patient",
                ]
                if any(kw in phrase for kw in relevant_keywords):
                    discoveries["uncategorized"].append({
                        "phrase": phrase,
                        "count": count,
                    })

        return discoveries

    def analyze_corpus(
        self,
        comments: Optional[List[Dict]] = None,
        output_dir: Optional[Path] = None,
    ) -> Dict[str, Path]:
        """
        Full frame analysis of comment corpus.

        Args:
            comments: List of comment dicts
            output_dir: Output directory

        Returns:
            Dict of output file paths
        """
        if comments is None:
            comments = self.data_loader.load_comments_json()

        if output_dir is None:
            output_dir = config.PROCESSED_DIR

        config.ensure_directories()

        output_files = {}

        # Analyze each comment
        frame_results = []
        frame_totals = Counter()

        for comment in comments:
            text = comment.get("full_text", comment.get("comment_text", ""))
            comment_id = comment.get("id", "")

            frames = self.detect_frames(text)

            # Determine dominant frame
            dominant = max(frames.items(), key=lambda x: x[1]["score"])
            dominant_frame = dominant[0] if dominant[1]["score"] > 0 else "none"

            result = {
                "comment_id": comment_id,
                "dominant_frame": dominant_frame,
                "word_count": comment.get("word_count", 0),
                "comment_type": comment.get("classification", {}).get("type", ""),
            }

            # Add individual frame scores
            for frame_id, frame_data in frames.items():
                result[f"{frame_id}_score"] = frame_data["score"]
                result[f"{frame_id}_present"] = frame_data["present"]
                if frame_data["present"]:
                    frame_totals[frame_id] += 1

            frame_results.append(result)

        # Export frame analysis
        df = pd.DataFrame(frame_results)
        path = output_dir / "frame_analysis.csv"
        df.to_csv(path, index=False)
        output_files["frame_analysis"] = path

        # Frame distribution summary
        distribution = {
            "total_comments": len(comments),
            "frame_counts": dict(frame_totals),
            "frame_percentages": {
                k: round(v / len(comments) * 100, 2)
                for k, v in frame_totals.items()
            },
        }

        # Cross-tabulation with comment type
        if "comment_type" in df.columns:
            crosstab = {}
            for ctype in df["comment_type"].unique():
                type_df = df[df["comment_type"] == ctype]
                type_frames = {}
                for frame_id in self.frames:
                    type_frames[frame_id] = int(type_df[f"{frame_id}_present"].sum())
                crosstab[ctype] = type_frames
            distribution["by_comment_type"] = crosstab

        path = output_dir / "four_frame_distribution.json"
        self.data_loader.save_json(distribution, path)
        output_files["frame_distribution"] = path

        # Possessive frame analysis
        logger.info("Analyzing possessive constructions by frame...")
        all_possessive_frames = defaultdict(list)

        for comment in comments[:500]:  # Sample for detailed analysis
            text = comment.get("full_text", comment.get("comment_text", ""))
            comment_id = comment.get("id", "")

            poss_frames = self.analyze_possessive_frames(text)
            for frame_id, contexts in poss_frames.items():
                for ctx in contexts:
                    ctx["comment_id"] = comment_id
                    all_possessive_frames[frame_id].append(ctx)

        # Export possessive frame analysis
        poss_summary = {
            frame_id: {
                "count": len(contexts),
                "examples": contexts[:20],  # Limit examples
            }
            for frame_id, contexts in all_possessive_frames.items()
        }

        path = output_dir / "possessive_frame_analysis.json"
        self.data_loader.save_json(poss_summary, path)
        output_files["possessive_frames"] = path

        # Run discovery mode
        logger.info("Running discovery mode...")
        discoveries = self.run_discovery_mode(comments)
        path = output_dir / "frame_discovery.json"
        self.data_loader.save_json(discoveries, path)
        output_files["discoveries"] = path

        logger.info(f"Frame analysis complete. Generated {len(output_files)} files.")
        return output_files

    def targeted_search(
        self,
        comments: List[Dict],
        frame_id: str,
        min_score: int = 3,
    ) -> List[Dict]:
        """
        Targeted search for comments strongly exhibiting a frame.

        Args:
            comments: List of comment dicts
            frame_id: Frame to search for
            min_score: Minimum frame score

        Returns:
            Filtered list of high-frame comments
        """
        results = []

        for comment in comments:
            text = comment.get("full_text", comment.get("comment_text", ""))
            frames = self.detect_frames(text)

            if frames.get(frame_id, {}).get("score", 0) >= min_score:
                results.append({
                    "comment_id": comment.get("id", ""),
                    "frame_score": frames[frame_id]["score"],
                    "matches": frames[frame_id]["matches"],
                    "text_preview": text[:500] + "..." if len(text) > 500 else text,
                })

        return sorted(results, key=lambda x: x["frame_score"], reverse=True)


def main():
    """Main entry point for frame detector."""
    import argparse

    parser = argparse.ArgumentParser(description="Detect rhetorical frames in FDA comments")
    parser.add_argument("--input", help="Input JSON file")
    parser.add_argument("--output-dir", help="Output directory")
    parser.add_argument("--discovery", action="store_true", help="Run discovery mode only")
    parser.add_argument("--search", help="Search for specific frame (body_self, product_drug, etc.)")
    parser.add_argument("--min-score", type=int, default=3, help="Minimum frame score for search")

    args = parser.parse_args()

    detector = FrameDetector()

    input_path = Path(args.input) if args.input else None
    comments = detector.data_loader.load_comments_json(input_path)

    if not comments:
        logger.error("No comments found")
        return

    if args.discovery:
        discoveries = detector.run_discovery_mode(comments)
        print(json.dumps(discoveries, indent=2))

    elif args.search:
        results = detector.targeted_search(comments, args.search, args.min_score)
        print(f"Found {len(results)} comments with strong {args.search} framing:")
        for r in results[:20]:
            print(f"  {r['comment_id']}: score={r['frame_score']}")

    else:
        output_dir = Path(args.output_dir) if args.output_dir else None
        output_files = detector.analyze_corpus(comments, output_dir)
        print(f"\nGenerated {len(output_files)} files:")
        for name, path in output_files.items():
            print(f"  - {name}: {path}")


if __name__ == "__main__":
    main()
