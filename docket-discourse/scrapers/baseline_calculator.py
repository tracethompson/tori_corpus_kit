"""
Tool 3: Baseline Calculator

Sample FDA dockets to calculate baseline comment volume statistics.
Generates comparison visualization showing where target docket falls.
"""
import logging
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from datetime import datetime
import time
import json

import requests
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from utils import config
from utils.data_loader import DataLoader

logging.basicConfig(level=logging.INFO, format=config.LOG_FORMAT)
logger = logging.getLogger(__name__)


class BaselineCalculator:
    """Calculate baseline statistics for FDA comment volumes."""

    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize calculator.

        Args:
            api_key: regulations.gov API key
        """
        self.api_key = api_key or config.REGULATIONS_GOV_API_KEY
        if not self.api_key:
            raise ValueError("API key required")

        self.base_url = config.REGULATIONS_API_BASE
        self.rate_limit_delay = config.RATE_LIMIT_DELAY
        self.data_loader = DataLoader()

    def _make_request(
        self, endpoint: str, params: Optional[Dict] = None
    ) -> Optional[Dict]:
        """Make API request with rate limiting."""
        url = f"{self.base_url}{endpoint}"

        if params is None:
            params = {}
        params["api_key"] = self.api_key

        try:
            response = requests.get(url, params=params, timeout=30)
            response.raise_for_status()
            time.sleep(self.rate_limit_delay)
            return response.json()

        except requests.exceptions.HTTPError as e:
            if response.status_code == 429:
                logger.warning("Rate limit hit. Waiting 60 seconds...")
                time.sleep(60)
                return self._make_request(endpoint, params)
            logger.error(f"HTTP error: {e}")
            return None

        except requests.exceptions.RequestException as e:
            logger.error(f"Request error: {e}")
            return None

    def sample_fda_dockets(
        self,
        sample_size: int = 200,
        start_date: str = "2014-01-01",
        docket_types: Optional[List[str]] = None,
    ) -> List[Dict]:
        """
        Sample FDA dockets to build baseline statistics.

        Args:
            sample_size: Number of dockets to sample
            start_date: Start date for sampling
            docket_types: Types of dockets to include

        Returns:
            List of docket data with comment counts
        """
        dockets = []
        page = 1
        page_size = 25

        logger.info(f"Sampling {sample_size} FDA dockets...")

        while len(dockets) < sample_size:
            params = {
                "filter[agencyId]": "FDA",
                "filter[postedDate][ge]": start_date,
                "page[size]": page_size,
                "page[number]": page,
            }

            result = self._make_request("/dockets", params)
            if not result:
                break

            data = result.get("data", [])
            if not data:
                break

            for item in data:
                if len(dockets) >= sample_size:
                    break

                attrs = item.get("attributes", {})
                docket_id = item.get("id", "")

                # Get comment count for this docket
                comment_count = self._get_comment_count(docket_id)

                docket_info = {
                    "id": docket_id,
                    "title": attrs.get("title", ""),
                    "docket_type": attrs.get("docketType", ""),
                    "modify_date": attrs.get("modifyDate", ""),
                    "comment_count": comment_count,
                }

                dockets.append(docket_info)
                logger.info(f"Sampled {len(dockets)}/{sample_size}: {docket_id} ({comment_count} comments)")

            meta = result.get("meta", {})
            total_pages = meta.get("totalPages", 1)

            if page >= total_pages:
                break
            page += 1

        return dockets

    def _get_comment_count(self, docket_id: str) -> int:
        """Get comment count for a docket."""
        params = {
            "filter[docketId]": docket_id,
            "page[size]": 1,
        }

        result = self._make_request("/comments", params)
        if not result:
            return 0

        meta = result.get("meta", {})
        return meta.get("totalElements", 0)

    def calculate_statistics(self, dockets: List[Dict]) -> Dict:
        """
        Calculate baseline statistics from sampled dockets.

        Args:
            dockets: List of docket data with comment counts

        Returns:
            Statistics dictionary
        """
        comment_counts = [d["comment_count"] for d in dockets]

        # Filter out dockets with 0 comments for certain statistics
        nonzero_counts = [c for c in comment_counts if c > 0]

        stats = {
            "sample_size": len(dockets),
            "dockets_with_comments": len(nonzero_counts),
            "mean": np.mean(comment_counts),
            "median": np.median(comment_counts),
            "std": np.std(comment_counts),
            "min": min(comment_counts),
            "max": max(comment_counts),
            "percentiles": {
                "25th": np.percentile(comment_counts, 25),
                "50th": np.percentile(comment_counts, 50),
                "75th": np.percentile(comment_counts, 75),
                "90th": np.percentile(comment_counts, 90),
                "95th": np.percentile(comment_counts, 95),
                "99th": np.percentile(comment_counts, 99),
            },
        }

        # Calculate percentile for target docket
        target_count = config.EXPECTED_COMMENT_COUNT
        stats["target_docket"] = {
            "id": config.DOCKET_ID,
            "comment_count": target_count,
            "percentile": self._calculate_percentile(comment_counts, target_count),
        }

        return stats

    def _calculate_percentile(self, values: List[int], target: int) -> float:
        """Calculate what percentile a target value falls in."""
        below = sum(1 for v in values if v < target)
        return (below / len(values)) * 100 if values else 0

    def generate_comparison_chart(
        self,
        dockets: List[Dict],
        stats: Dict,
        output_path: Optional[Path] = None,
    ) -> Path:
        """
        Generate visualization comparing target docket to baseline.

        Args:
            dockets: Sampled docket data
            stats: Calculated statistics
            output_path: Output file path

        Returns:
            Path to saved figure
        """
        if output_path is None:
            output_path = config.FIGURES_DIR / "baseline_comparison.png"

        config.ensure_directories()

        comment_counts = [d["comment_count"] for d in dockets]
        target_count = stats["target_docket"]["comment_count"]

        fig, axes = plt.subplots(1, 2, figsize=(14, 5))

        # Histogram with log scale
        ax1 = axes[0]
        # Filter to show relevant range
        filtered_counts = [c for c in comment_counts if c > 0]

        ax1.hist(filtered_counts, bins=50, edgecolor="black", alpha=0.7, color="steelblue")
        ax1.axvline(target_count, color="red", linestyle="--", linewidth=2,
                   label=f"FDA-2015-D-3719 ({target_count:,})")
        ax1.axvline(stats["median"], color="green", linestyle=":", linewidth=2,
                   label=f"Median ({stats['median']:.0f})")

        ax1.set_xlabel("Number of Comments")
        ax1.set_ylabel("Number of Dockets")
        ax1.set_title("Distribution of FDA Docket Comment Volumes")
        ax1.legend()
        ax1.set_xscale("log")

        # Box plot comparison
        ax2 = axes[1]

        # Create categories
        categories = ["Sampled FDA\nDockets", f"FDA-2015-D-3719\n({target_count:,} comments)"]
        positions = [1, 2]

        bp = ax2.boxplot([filtered_counts], positions=[1], widths=0.6)
        ax2.scatter([2], [target_count], color="red", s=200, zorder=5, marker="*")

        ax2.set_ylabel("Number of Comments (log scale)")
        ax2.set_yscale("log")
        ax2.set_xlim(0.5, 2.5)
        ax2.set_xticks([1, 2])
        ax2.set_xticklabels(categories)
        ax2.set_title("Target Docket vs. FDA Baseline")

        # Add percentile annotation
        percentile = stats["target_docket"]["percentile"]
        ax2.annotate(
            f"{percentile:.1f}th percentile",
            xy=(2, target_count),
            xytext=(2.2, target_count * 1.5),
            arrowprops=dict(arrowstyle="->", color="red"),
            fontsize=10,
            color="red",
        )

        plt.tight_layout()
        plt.savefig(output_path, dpi=config.FIGURE_DPI, bbox_inches="tight")
        plt.savefig(output_path.with_suffix(".pdf"), bbox_inches="tight")
        plt.close()

        logger.info(f"Saved comparison chart to {output_path}")
        return output_path

    def generate_report(
        self,
        dockets: List[Dict],
        stats: Dict,
        output_path: Optional[Path] = None,
    ) -> Path:
        """
        Generate baseline statistics report.

        Args:
            dockets: Sampled docket data
            stats: Calculated statistics
            output_path: Output file path

        Returns:
            Path to saved report
        """
        if output_path is None:
            output_path = config.PROCESSED_DIR / "baseline_statistics.json"

        report = {
            "metadata": {
                "generated_at": datetime.now().isoformat(),
                "sample_size": stats["sample_size"],
                "target_docket": config.DOCKET_ID,
            },
            "statistics": stats,
            "interpretation": self._generate_interpretation(stats),
            "sample_data": dockets,
        }

        self.data_loader.save_json(report, output_path)
        logger.info(f"Saved baseline report to {output_path}")

        # Also save CSV of sampled dockets
        csv_path = config.PROCESSED_DIR / "sampled_dockets.csv"
        self.data_loader.save_csv(dockets, csv_path)

        return output_path

    def _generate_interpretation(self, stats: Dict) -> Dict:
        """Generate human-readable interpretation of statistics."""
        target = stats["target_docket"]
        percentile = target["percentile"]

        if percentile >= 99:
            significance = "extremely unusual"
        elif percentile >= 95:
            significance = "highly unusual"
        elif percentile >= 90:
            significance = "notably high"
        elif percentile >= 75:
            significance = "above average"
        else:
            significance = "typical"

        return {
            "summary": (
                f"Docket {target['id']} received {target['comment_count']:,} comments, "
                f"placing it in the {percentile:.1f}th percentile of FDA dockets. "
                f"This is {significance} for FDA regulatory proceedings."
            ),
            "comparison_to_median": (
                f"The target docket received {target['comment_count'] / stats['median']:.1f}x "
                f"more comments than the median FDA docket ({stats['median']:.0f} comments)."
            ),
            "significance_level": significance,
        }

    def run_full_analysis(
        self,
        sample_size: int = 200,
        use_cached: bool = True,
    ) -> Tuple[List[Dict], Dict]:
        """
        Run complete baseline analysis.

        Args:
            sample_size: Number of dockets to sample
            use_cached: Use cached data if available

        Returns:
            Tuple of (dockets, statistics)
        """
        config.ensure_directories()

        cache_path = config.PROCESSED_DIR / "sampled_dockets_cache.json"

        # Check for cached data
        if use_cached and cache_path.exists():
            logger.info("Loading cached docket data...")
            with open(cache_path, "r") as f:
                dockets = json.load(f)
        else:
            dockets = self.sample_fda_dockets(sample_size)
            self.data_loader.save_json(dockets, cache_path)

        stats = self.calculate_statistics(dockets)
        self.generate_comparison_chart(dockets, stats)
        self.generate_report(dockets, stats)

        return dockets, stats


def main():
    """Main entry point for baseline calculator."""
    import argparse

    parser = argparse.ArgumentParser(description="Calculate FDA docket baseline statistics")
    parser.add_argument("--sample-size", type=int, default=200, help="Number of dockets to sample")
    parser.add_argument("--no-cache", action="store_true", help="Don't use cached data")
    parser.add_argument("--stats-only", action="store_true", help="Only calculate stats from cached data")

    args = parser.parse_args()

    calculator = BaselineCalculator()

    if args.stats_only:
        cache_path = config.PROCESSED_DIR / "sampled_dockets_cache.json"
        if cache_path.exists():
            with open(cache_path, "r") as f:
                dockets = json.load(f)
            stats = calculator.calculate_statistics(dockets)
            print(json.dumps(stats, indent=2))
        else:
            logger.error("No cached data found. Run full analysis first.")
    else:
        dockets, stats = calculator.run_full_analysis(
            sample_size=args.sample_size,
            use_cached=not args.no_cache,
        )

        print("\n=== BASELINE STATISTICS ===")
        print(f"Sample size: {stats['sample_size']} dockets")
        print(f"Mean comments: {stats['mean']:.1f}")
        print(f"Median comments: {stats['median']:.1f}")
        print(f"Std deviation: {stats['std']:.1f}")
        print(f"\n95th percentile: {stats['percentiles']['95th']:.0f}")
        print(f"99th percentile: {stats['percentiles']['99th']:.0f}")
        print(f"\nTarget docket ({config.DOCKET_ID}):")
        print(f"  Comments: {stats['target_docket']['comment_count']:,}")
        print(f"  Percentile: {stats['target_docket']['percentile']:.1f}th")


if __name__ == "__main__":
    main()
