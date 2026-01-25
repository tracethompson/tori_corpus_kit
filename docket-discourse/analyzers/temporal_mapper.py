"""
Tool 7: Temporal Mapper

Analyze submission patterns over time.
Includes MinHash/LSH duplicate detection to identify form letters vs unique arguments.
"""
import logging
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Set
from collections import Counter, defaultdict
from datetime import datetime, timedelta
import json
import re

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.dates as mdates

try:
    from datasketch import MinHash, MinHashLSH
    DATASKETCH_AVAILABLE = True
except ImportError:
    DATASKETCH_AVAILABLE = False

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from utils import config
from utils.data_loader import DataLoader

logging.basicConfig(level=logging.INFO, format=config.LOG_FORMAT)
logger = logging.getLogger(__name__)


class TemporalMapper:
    """Map comment submissions over time and detect duplicates."""

    def __init__(self):
        """Initialize temporal mapper."""
        self.data_loader = DataLoader()

        # MinHash/LSH configuration
        self.num_perm = config.MINHASH_NUM_PERM
        self.similarity_threshold = config.SIMILARITY_THRESHOLD
        self.shingle_size = config.SHINGLE_SIZE

        # Key events for timeline
        self.key_events = [
            {"date": "2015-12-22", "label": "Docket Opens"},
            {"date": "2016-03-28", "label": "Comment Period Closes"},
        ]

    def _create_shingles(self, text: str, k: int = 3) -> Set[str]:
        """
        Create word-level shingles from text.

        Args:
            text: Input text
            k: Shingle size (number of words)

        Returns:
            Set of shingle strings
        """
        if not text:
            return set()

        # Normalize text
        text = re.sub(r"[^\w\s]", "", text.lower())
        words = text.split()

        if len(words) < k:
            return {" ".join(words)}

        shingles = set()
        for i in range(len(words) - k + 1):
            shingle = " ".join(words[i:i + k])
            shingles.add(shingle)

        return shingles

    def _create_minhash(self, text: str) -> Optional["MinHash"]:
        """
        Create MinHash signature for text.

        Args:
            text: Input text

        Returns:
            MinHash object or None
        """
        if not DATASKETCH_AVAILABLE:
            logger.warning("datasketch not available for MinHash")
            return None

        shingles = self._create_shingles(text, self.shingle_size)
        if not shingles:
            return None

        mh = MinHash(num_perm=self.num_perm)
        for shingle in shingles:
            mh.update(shingle.encode("utf-8"))

        return mh

    def detect_duplicates(
        self,
        comments: List[Dict],
        threshold: Optional[float] = None,
    ) -> Dict:
        """
        Detect near-duplicate comments using MinHash/LSH.

        Args:
            comments: List of comment dicts
            threshold: Similarity threshold (default from config)

        Returns:
            Duplicate detection results
        """
        if not DATASKETCH_AVAILABLE:
            return {"error": "datasketch library not installed"}

        if threshold is None:
            threshold = self.similarity_threshold

        logger.info(f"Detecting duplicates with threshold {threshold}...")

        # Create LSH index
        lsh = MinHashLSH(threshold=threshold, num_perm=self.num_perm)

        # Create MinHash for each comment
        minhashes = {}
        for comment in comments:
            comment_id = comment.get("id", "")
            text = comment.get("full_text", comment.get("comment_text", ""))

            mh = self._create_minhash(text)
            if mh:
                minhashes[comment_id] = mh
                try:
                    lsh.insert(comment_id, mh)
                except ValueError:
                    # Duplicate key
                    pass

        # Find duplicate groups
        processed = set()
        duplicate_groups = []

        for comment_id, mh in minhashes.items():
            if comment_id in processed:
                continue

            # Query for similar comments
            similar = lsh.query(mh)

            if len(similar) > 1:
                group = list(similar)
                duplicate_groups.append({
                    "group_id": len(duplicate_groups) + 1,
                    "size": len(group),
                    "comment_ids": group,
                })
                processed.update(group)
            else:
                processed.add(comment_id)

        # Calculate statistics
        total_in_groups = sum(g["size"] for g in duplicate_groups)
        unique_count = len(comments) - total_in_groups + len(duplicate_groups)

        results = {
            "total_comments": len(comments),
            "duplicate_groups": len(duplicate_groups),
            "comments_in_groups": total_in_groups,
            "unique_comments": unique_count,
            "duplicate_rate": round(total_in_groups / len(comments) * 100, 2) if comments else 0,
            "groups": duplicate_groups,
        }

        logger.info(f"Found {len(duplicate_groups)} duplicate groups "
                   f"({total_in_groups} comments, {results['duplicate_rate']:.1f}%)")

        return results

    def extract_group_samples(
        self,
        comments: List[Dict],
        duplicate_results: Dict,
        sample_per_group: int = 1,
    ) -> List[Dict]:
        """
        Extract representative samples from duplicate groups.

        Args:
            comments: List of comment dicts
            duplicate_results: Output from detect_duplicates
            sample_per_group: Number of samples per group

        Returns:
            List of sample comments with group info
        """
        # Create comment lookup
        comment_map = {c.get("id", ""): c for c in comments}

        samples = []
        for group in duplicate_results.get("groups", []):
            group_id = group["group_id"]
            comment_ids = group["comment_ids"]

            # Get first N from group
            for i, cid in enumerate(comment_ids[:sample_per_group]):
                comment = comment_map.get(cid, {})
                text = comment.get("full_text", comment.get("comment_text", ""))

                samples.append({
                    "group_id": group_id,
                    "group_size": group["size"],
                    "sample_index": i,
                    "comment_id": cid,
                    "text_preview": text[:500] + "..." if len(text) > 500 else text,
                    "posted_date": comment.get("posted_date", ""),
                })

        return samples

    def parse_date(self, date_str: str) -> Optional[datetime]:
        """Parse date string to datetime."""
        if not date_str:
            return None

        formats = [
            "%Y-%m-%dT%H:%M:%SZ",
            "%Y-%m-%d",
            "%m/%d/%Y",
        ]

        for fmt in formats:
            try:
                return datetime.strptime(date_str[:19], fmt[:len(date_str)])
            except ValueError:
                continue

        return None

    def build_timeline(
        self,
        comments: List[Dict],
    ) -> pd.DataFrame:
        """
        Build submission timeline.

        Args:
            comments: List of comment dicts

        Returns:
            DataFrame with daily submission counts
        """
        dates = []
        for comment in comments:
            date_str = comment.get("posted_date", "")
            parsed = self.parse_date(date_str)
            if parsed:
                dates.append(parsed.date())

        if not dates:
            return pd.DataFrame()

        # Count by date
        date_counts = Counter(dates)

        # Create DataFrame with all dates in range
        min_date = min(dates)
        max_date = max(dates)
        all_dates = []
        current = min_date

        while current <= max_date:
            all_dates.append({
                "date": current,
                "count": date_counts.get(current, 0),
            })
            current += timedelta(days=1)

        df = pd.DataFrame(all_dates)
        df["cumulative"] = df["count"].cumsum()
        df["day_of_week"] = pd.to_datetime(df["date"]).dt.day_name()

        return df

    def analyze_by_stakeholder(
        self,
        comments: List[Dict],
    ) -> Dict[str, pd.DataFrame]:
        """
        Analyze submission patterns by stakeholder type.

        Args:
            comments: List of comment dicts

        Returns:
            Dict of DataFrames by stakeholder type
        """
        # Group by stakeholder
        by_stakeholder = defaultdict(list)

        for comment in comments:
            stakeholder = comment.get("stakeholder", {}).get("category", "unknown")
            by_stakeholder[stakeholder].append(comment)

        # Build timeline for each
        timelines = {}
        for stakeholder, group_comments in by_stakeholder.items():
            if group_comments:
                timelines[stakeholder] = self.build_timeline(group_comments)

        return timelines

    def generate_timeline_chart(
        self,
        timeline: pd.DataFrame,
        output_path: Optional[Path] = None,
        title: str = "Comment Submission Timeline",
    ) -> Path:
        """
        Generate timeline visualization.

        Args:
            timeline: DataFrame from build_timeline
            output_path: Output file path
            title: Chart title

        Returns:
            Path to saved figure
        """
        if output_path is None:
            output_path = config.FIGURES_DIR / "submission_timeline.png"

        config.ensure_directories()

        fig, axes = plt.subplots(2, 1, figsize=(14, 8), sharex=True)

        # Daily submissions
        ax1 = axes[0]
        ax1.bar(timeline["date"], timeline["count"], color="steelblue", alpha=0.7)
        ax1.set_ylabel("Daily Submissions")
        ax1.set_title(title)

        # Add key events
        for event in self.key_events:
            event_date = datetime.strptime(event["date"], "%Y-%m-%d").date()
            ax1.axvline(event_date, color="red", linestyle="--", alpha=0.7)
            ax1.annotate(
                event["label"],
                xy=(event_date, ax1.get_ylim()[1] * 0.9),
                fontsize=9,
                color="red",
            )

        # Cumulative submissions
        ax2 = axes[1]
        ax2.plot(timeline["date"], timeline["cumulative"], color="darkgreen", linewidth=2)
        ax2.fill_between(timeline["date"], timeline["cumulative"], alpha=0.3, color="green")
        ax2.set_ylabel("Cumulative Submissions")
        ax2.set_xlabel("Date")

        # Format x-axis
        ax2.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m-%d"))
        ax2.xaxis.set_major_locator(mdates.WeekdayLocator(interval=2))
        plt.xticks(rotation=45)

        plt.tight_layout()
        plt.savefig(output_path, dpi=config.FIGURE_DPI, bbox_inches="tight")
        plt.savefig(output_path.with_suffix(".pdf"), bbox_inches="tight")
        plt.close()

        logger.info(f"Saved timeline chart to {output_path}")
        return output_path

    def run_full_analysis(
        self,
        comments: Optional[List[Dict]] = None,
        output_dir: Optional[Path] = None,
    ) -> Dict[str, Path]:
        """
        Run complete temporal analysis.

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

        # Build timeline
        logger.info("Building submission timeline...")
        timeline = self.build_timeline(comments)

        if not timeline.empty:
            path = output_dir / "submission_timeline.csv"
            timeline.to_csv(path, index=False)
            output_files["timeline"] = path

            # Generate chart
            chart_path = self.generate_timeline_chart(timeline)
            output_files["timeline_chart"] = chart_path

        # Detect duplicates
        logger.info("Detecting duplicate comments...")
        duplicates = self.detect_duplicates(comments)

        path = output_dir / "duplicate_analysis.json"
        self.data_loader.save_json(duplicates, path)
        output_files["duplicate_analysis"] = path

        # Export duplicate groups
        if duplicates.get("groups"):
            groups_df = pd.DataFrame(duplicates["groups"])
            path = output_dir / "duplicate_comment_groups.csv"
            groups_df.to_csv(path, index=False)
            output_files["duplicate_groups"] = path

            # Extract samples
            samples = self.extract_group_samples(comments, duplicates)
            path = output_dir / "duplicate_group_samples.csv"
            pd.DataFrame(samples).to_csv(path, index=False)
            output_files["group_samples"] = path

        # Unique arguments analysis
        logger.info("Analyzing unique vs form letter ratio...")

        # Get IDs of comments in duplicate groups
        grouped_ids = set()
        for group in duplicates.get("groups", []):
            grouped_ids.update(group["comment_ids"])

        unique_comments = [c for c in comments if c.get("id", "") not in grouped_ids]

        unique_analysis = {
            "total_comments": len(comments),
            "unique_arguments": len(unique_comments),
            "form_letter_groups": duplicates.get("duplicate_groups", 0),
            "comments_in_form_letters": len(grouped_ids),
            "uniqueness_ratio": round(len(unique_comments) / len(comments) * 100, 2) if comments else 0,
            "avg_group_size": (
                sum(g["size"] for g in duplicates.get("groups", [])) /
                len(duplicates.get("groups", [])) if duplicates.get("groups") else 0
            ),
        }

        path = output_dir / "unique_arguments_analysis.json"
        self.data_loader.save_json(unique_analysis, path)
        output_files["unique_analysis"] = path

        # Day of week analysis
        if not timeline.empty:
            dow_counts = timeline.groupby("day_of_week")["count"].sum()
            path = output_dir / "submissions_by_day_of_week.csv"
            dow_counts.to_csv(path)
            output_files["day_of_week"] = path

        logger.info(f"Temporal analysis complete. Generated {len(output_files)} files.")
        return output_files


def main():
    """Main entry point for temporal mapper."""
    import argparse

    parser = argparse.ArgumentParser(description="Analyze FDA comment temporal patterns")
    parser.add_argument("--input", help="Input JSON file")
    parser.add_argument("--output-dir", help="Output directory")
    parser.add_argument("--duplicates-only", action="store_true",
                       help="Only run duplicate detection")
    parser.add_argument("--threshold", type=float, default=0.9,
                       help="Similarity threshold for duplicates")

    args = parser.parse_args()

    mapper = TemporalMapper()

    if args.threshold != 0.9:
        mapper.similarity_threshold = args.threshold

    input_path = Path(args.input) if args.input else None
    comments = mapper.data_loader.load_comments_json(input_path)

    if not comments:
        logger.error("No comments found")
        return

    if args.duplicates_only:
        results = mapper.detect_duplicates(comments)
        print(json.dumps({k: v for k, v in results.items() if k != "groups"}, indent=2))
        print(f"\nFound {len(results.get('groups', []))} duplicate groups")
    else:
        output_dir = Path(args.output_dir) if args.output_dir else None
        output_files = mapper.run_full_analysis(comments, output_dir)
        print(f"\nGenerated {len(output_files)} files:")
        for name, path in output_files.items():
            print(f"  - {name}: {path}")


if __name__ == "__main__":
    main()
