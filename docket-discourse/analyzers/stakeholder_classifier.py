"""
Tool 6: Stakeholder Classifier

Classify FDA public comment authors by stakeholder type.
Uses multi-signal approach: keywords, possessives, technical density, credentials.
"""
import logging
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from collections import Counter
import re
import json

import pandas as pd

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from utils import config
from utils.data_loader import DataLoader
from utils.comment_classifier import CommentClassifier

logging.basicConfig(level=logging.INFO, format=config.LOG_FORMAT)
logger = logging.getLogger(__name__)


class StakeholderClassifier:
    """Classify comment authors by stakeholder type."""

    def __init__(self, keywords_path: Optional[Path] = None):
        """
        Initialize classifier.

        Args:
            keywords_path: Path to stakeholder keywords JSON
        """
        self.data_loader = DataLoader()
        self.comment_classifier = CommentClassifier()

        # Load stakeholder keywords
        if keywords_path is None:
            keywords_path = config.DICTIONARIES_DIR / "stakeholder_keywords.json"

        self.keywords_data = self._load_keywords(keywords_path)
        self.categories = self.keywords_data.get("stakeholder_categories", {})
        self.rules = self.keywords_data.get("classification_rules", {})
        self.exclusions = self.keywords_data.get("exclusion_patterns", {})

    def _load_keywords(self, path: Path) -> Dict:
        """Load stakeholder keywords dictionary."""
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError) as e:
            logger.warning(f"Could not load keywords: {e}")
            return {}

    def extract_credentials(self, text: str) -> List[str]:
        """
        Extract professional credentials from text.

        Args:
            text: Input text

        Returns:
            List of detected credentials
        """
        credentials = []

        # Common credential patterns
        credential_patterns = [
            r"\b(M\.?D\.?)\b",
            r"\b(D\.?O\.?)\b",
            r"\b(Ph\.?D\.?)\b",
            r"\b(J\.?D\.?)\b",
            r"\b(R\.?N\.?)\b",
            r"\b(N\.?P\.?)\b",
            r"\b(P\.?A\.?)\b",
            r"\b(Esq\.?)\b",
            r"\b(CEO|COO|CFO)\b",
            r"\b(President|Vice President|Director)\b",
        ]

        for pattern in credential_patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            credentials.extend(matches)

        return list(set(credentials))

    def calculate_category_score(
        self,
        text: str,
        category_id: str,
        possessive_count: int,
        technical_density: float,
        credentials: List[str],
    ) -> Tuple[float, List[str]]:
        """
        Calculate score for a specific stakeholder category.

        Args:
            text: Input text
            category_id: Category to score
            possessive_count: Pre-calculated possessive count
            technical_density: Pre-calculated technical density
            credentials: Pre-extracted credentials

        Returns:
            Tuple of (score, matched_signals)
        """
        category = self.categories.get(category_id, {})
        if not category:
            return 0.0, []

        text_lower = text.lower()
        score = 0.0
        signals = []

        # Keyword matching
        keywords = category.get("keywords", [])
        keyword_matches = sum(1 for kw in keywords if kw.lower() in text_lower)
        if keyword_matches > 0:
            score += keyword_matches * 1.0
            signals.append(f"keywords:{keyword_matches}")

        # Possessive language weight
        poss_weight = category.get("possessive_weight", 1.0)
        if poss_weight > 0 and possessive_count > 3:
            score += poss_weight
            signals.append(f"possessives:{possessive_count}")

        # Technical density check
        tech_min = category.get("technical_density_min")
        tech_max = category.get("technical_density_max")

        if tech_min is not None and technical_density >= tech_min:
            score += 1.0
            signals.append(f"tech_density_high:{technical_density:.1f}")
        if tech_max is not None and technical_density <= tech_max:
            score += 0.5
            signals.append(f"tech_density_low:{technical_density:.1f}")

        # Credential matching
        category_creds = category.get("credential_patterns", [])
        cred_matches = [c for c in credentials if any(
            pattern.lower() in c.lower() for pattern in category_creds
        )]
        if cred_matches:
            boost = self.rules.get("credential_boost", 1.5)
            score += boost * len(cred_matches)
            signals.append(f"credentials:{','.join(cred_matches)}")

        # Organizational indicator check
        if category.get("organizational_indicators"):
            org_patterns = [
                r"on\s+behalf\s+of",
                r"our\s+(organization|company|clinic|association)",
                r"we\s+(submit|respectfully|urge)",
            ]
            for pattern in org_patterns:
                if re.search(pattern, text_lower):
                    score += 1.0
                    signals.append("organizational_language")
                    break

        return score, signals

    def classify_stakeholder(self, text: str, submitter_name: str = "") -> Dict:
        """
        Classify a comment author's stakeholder type.

        Args:
            text: Comment text
            submitter_name: Submitter name if available

        Returns:
            Classification result dict
        """
        if not text:
            return {
                "category": "unknown",
                "confidence": "low",
                "score": 0,
                "signals": [],
            }

        # Pre-calculate common metrics
        possessive_count = self.comment_classifier.count_possessive_language(text)
        technical_density = self.comment_classifier.calculate_technical_density(text)
        credentials = self.extract_credentials(text)

        # Also check credentials in submitter name
        if submitter_name:
            credentials.extend(self.extract_credentials(submitter_name))
            credentials = list(set(credentials))

        # Score each category
        category_scores = {}
        category_signals = {}

        for category_id in self.categories:
            score, signals = self.calculate_category_score(
                text, category_id,
                possessive_count, technical_density, credentials
            )
            category_scores[category_id] = score
            category_signals[category_id] = signals

        # Apply exclusion rules
        for exclusion_key, patterns in self.exclusions.items():
            if not exclusion_key.endswith("_excludes_patient"):
                continue

            excluder = exclusion_key.replace("_excludes_patient", "")
            text_lower = text.lower()

            if any(p.lower() in text_lower for p in patterns):
                # Reduce patient score if organizational language present
                if "patient" in category_scores:
                    category_scores["patient"] *= 0.5

        # Determine winner
        if not category_scores:
            return {
                "category": "unknown",
                "confidence": "low",
                "score": 0,
                "signals": [],
            }

        best_category = max(category_scores, key=category_scores.get)
        best_score = category_scores[best_category]

        # Calculate confidence
        thresholds = self.rules.get("confidence_thresholds", {
            "high": 0.8,
            "medium": 0.5,
            "low": 0.3,
        })

        # Normalize score
        max_possible = 10.0  # Rough estimate
        normalized = min(1.0, best_score / max_possible)

        if normalized >= thresholds["high"]:
            confidence = "high"
        elif normalized >= thresholds["medium"]:
            confidence = "medium"
        else:
            confidence = "low"

        # Check minimum signals requirement
        min_signals = self.rules.get("min_keyword_matches", 2)
        if len(category_signals.get(best_category, [])) < min_signals:
            confidence = "low"

        return {
            "category": best_category,
            "confidence": confidence,
            "score": round(best_score, 2),
            "normalized_score": round(normalized, 2),
            "signals": category_signals.get(best_category, []),
            "all_scores": {k: round(v, 2) for k, v in category_scores.items()},
            "credentials_found": credentials,
            "possessive_count": possessive_count,
            "technical_density": round(technical_density, 2),
        }

    def classify_corpus(
        self,
        comments: Optional[List[Dict]] = None,
        output_dir: Optional[Path] = None,
        high_confidence_only: bool = True,
    ) -> Dict[str, Path]:
        """
        Classify all comments in corpus.

        Args:
            comments: List of comment dicts
            output_dir: Output directory
            high_confidence_only: Only output high confidence classifications

        Returns:
            Dict of output file paths
        """
        if comments is None:
            comments = self.data_loader.load_comments_json()

        if output_dir is None:
            output_dir = config.PROCESSED_DIR

        config.ensure_directories()

        output_files = {}
        results = []
        category_counts = Counter()
        confidence_counts = Counter()

        for comment in comments:
            text = comment.get("full_text", comment.get("comment_text", ""))
            submitter = comment.get("submitter_name", "")
            comment_id = comment.get("id", "")

            classification = self.classify_stakeholder(text, submitter)

            result = {
                "comment_id": comment_id,
                "submitter_name": submitter,
                "stakeholder_category": classification["category"],
                "confidence": classification["confidence"],
                "score": classification["score"],
                "signals": "; ".join(classification["signals"]),
                "credentials": ", ".join(classification["credentials_found"]),
                "word_count": comment.get("word_count", 0),
                "comment_type": comment.get("classification", {}).get("type", ""),
            }

            results.append(result)
            category_counts[classification["category"]] += 1
            confidence_counts[classification["confidence"]] += 1

        # Export all classifications
        df = pd.DataFrame(results)
        path = output_dir / "stakeholder_classifications_all.csv"
        df.to_csv(path, index=False)
        output_files["all_classifications"] = path

        # Export high confidence only
        if high_confidence_only:
            high_conf = df[df["confidence"] == "high"]
            path = output_dir / "stakeholder_classifications_high_confidence.csv"
            high_conf.to_csv(path, index=False)
            output_files["high_confidence"] = path
            logger.info(f"High confidence classifications: {len(high_conf)}")

        # Export unknowns for manual review
        unknowns = df[(df["stakeholder_category"] == "unknown") |
                      (df["confidence"] == "low")]
        if len(unknowns) > 0:
            path = output_dir / "stakeholder_manual_review.csv"
            unknowns.to_csv(path, index=False)
            output_files["manual_review"] = path
            logger.info(f"Flagged for manual review: {len(unknowns)}")

        # Summary statistics
        summary = {
            "total_classified": len(results),
            "category_distribution": dict(category_counts),
            "confidence_distribution": dict(confidence_counts),
            "high_confidence_count": confidence_counts.get("high", 0),
            "category_percentages": {
                k: round(v / len(results) * 100, 2)
                for k, v in category_counts.items()
            },
        }

        # Cross-tabulation with comment type
        if "comment_type" in df.columns:
            crosstab = pd.crosstab(df["stakeholder_category"], df["comment_type"])
            path = output_dir / "stakeholder_by_comment_type.csv"
            crosstab.to_csv(path)
            output_files["crosstab"] = path

        path = output_dir / "stakeholder_summary.json"
        self.data_loader.save_json(summary, path)
        output_files["summary"] = path

        logger.info(f"Stakeholder classification complete. Generated {len(output_files)} files.")
        return output_files

    def validate_sample(
        self,
        comments: List[Dict],
        sample_size: int = 50,
    ) -> List[Dict]:
        """
        Generate sample for manual validation.

        Args:
            comments: List of comment dicts
            sample_size: Number to sample

        Returns:
            Sample with classifications for review
        """
        import random

        sample = random.sample(comments, min(sample_size, len(comments)))
        validation_set = []

        for comment in sample:
            text = comment.get("full_text", comment.get("comment_text", ""))
            submitter = comment.get("submitter_name", "")
            comment_id = comment.get("id", "")

            classification = self.classify_stakeholder(text, submitter)

            validation_set.append({
                "comment_id": comment_id,
                "submitter_name": submitter,
                "text_preview": text[:500] + "..." if len(text) > 500 else text,
                "predicted_category": classification["category"],
                "confidence": classification["confidence"],
                "signals": classification["signals"],
                "manual_category": "",  # For human reviewer to fill
                "notes": "",  # For reviewer notes
            })

        return validation_set


def main():
    """Main entry point for stakeholder classifier."""
    import argparse

    parser = argparse.ArgumentParser(description="Classify FDA comment stakeholders")
    parser.add_argument("--input", help="Input JSON file")
    parser.add_argument("--output-dir", help="Output directory")
    parser.add_argument("--all-confidence", action="store_true",
                       help="Output all confidence levels, not just high")
    parser.add_argument("--validate", type=int, help="Generate validation sample of N comments")

    args = parser.parse_args()

    classifier = StakeholderClassifier()

    input_path = Path(args.input) if args.input else None
    comments = classifier.data_loader.load_comments_json(input_path)

    if not comments:
        logger.error("No comments found")
        return

    if args.validate:
        sample = classifier.validate_sample(comments, args.validate)
        output_path = config.PROCESSED_DIR / "stakeholder_validation_sample.json"
        classifier.data_loader.save_json(sample, output_path)
        print(f"Generated validation sample: {output_path}")

    else:
        output_dir = Path(args.output_dir) if args.output_dir else None
        output_files = classifier.classify_corpus(
            comments, output_dir,
            high_confidence_only=not args.all_confidence
        )
        print(f"\nGenerated {len(output_files)} files:")
        for name, path in output_files.items():
            print(f"  - {name}: {path}")


if __name__ == "__main__":
    main()
