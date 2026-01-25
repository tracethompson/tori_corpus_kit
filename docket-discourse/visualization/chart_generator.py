"""
Supporting Visualization: Chart Generator

Generate publication-quality figures for FDA comment analysis.
Outputs at 300dpi PNG and vector PDF formats.
"""
import logging
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import json

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import seaborn as sns

try:
    import networkx as nx
    NETWORKX_AVAILABLE = True
except ImportError:
    NETWORKX_AVAILABLE = False

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from utils import config
from utils.data_loader import DataLoader

logging.basicConfig(level=logging.INFO, format=config.LOG_FORMAT)
logger = logging.getLogger(__name__)

# Set style
plt.style.use("seaborn-v0_8-whitegrid")
sns.set_palette("husl")


class ChartGenerator:
    """Generate publication-quality charts."""

    def __init__(self):
        """Initialize chart generator."""
        self.data_loader = DataLoader()
        self.dpi = config.FIGURE_DPI
        self.figures_dir = config.FIGURES_DIR

    def _save_figure(self, fig: plt.Figure, name: str) -> Tuple[Path, Path]:
        """Save figure in both raster and vector formats."""
        config.ensure_directories()

        png_path = self.figures_dir / f"{name}.png"
        pdf_path = self.figures_dir / f"{name}.pdf"

        fig.savefig(png_path, dpi=self.dpi, bbox_inches="tight", facecolor="white")
        fig.savefig(pdf_path, bbox_inches="tight", facecolor="white")
        plt.close(fig)

        logger.info(f"Saved figure: {name}")
        return png_path, pdf_path

    def comment_type_distribution(
        self,
        comments: List[Dict],
        name: str = "comment_type_distribution",
    ) -> Tuple[Path, Path]:
        """
        Create pie/bar chart of comment type distribution.

        Args:
            comments: List of comment dicts
            name: Output filename

        Returns:
            Tuple of (png_path, pdf_path)
        """
        # Count types
        type_counts = {}
        for comment in comments:
            ctype = comment.get("classification", {}).get("type", "unknown")
            type_counts[ctype] = type_counts.get(ctype, 0) + 1

        labels = list(type_counts.keys())
        sizes = list(type_counts.values())

        # Create figure
        fig, axes = plt.subplots(1, 2, figsize=(12, 5))

        # Pie chart
        ax1 = axes[0]
        colors = sns.color_palette("husl", len(labels))
        wedges, texts, autotexts = ax1.pie(
            sizes, labels=labels, autopct="%1.1f%%",
            colors=colors, startangle=90
        )
        ax1.set_title("Comment Type Distribution")

        # Bar chart
        ax2 = axes[1]
        bars = ax2.bar(labels, sizes, color=colors)
        ax2.set_xlabel("Comment Type")
        ax2.set_ylabel("Number of Comments")
        ax2.set_title("Comment Counts by Type")

        # Add value labels on bars
        for bar, count in zip(bars, sizes):
            ax2.annotate(
                f"{count:,}",
                xy=(bar.get_x() + bar.get_width() / 2, bar.get_height()),
                ha="center", va="bottom", fontsize=10
            )

        plt.tight_layout()
        return self._save_figure(fig, name)

    def stakeholder_distribution(
        self,
        comments: List[Dict],
        name: str = "stakeholder_distribution",
    ) -> Tuple[Path, Path]:
        """
        Create horizontal bar chart of stakeholder types.

        Args:
            comments: List of comment dicts
            name: Output filename

        Returns:
            Tuple of (png_path, pdf_path)
        """
        # Count stakeholders
        stakeholder_counts = {}
        for comment in comments:
            stakeholder = comment.get("stakeholder", {}).get("category", "unknown")
            stakeholder_counts[stakeholder] = stakeholder_counts.get(stakeholder, 0) + 1

        # Sort by count
        sorted_items = sorted(stakeholder_counts.items(), key=lambda x: x[1], reverse=True)
        labels = [item[0] for item in sorted_items]
        counts = [item[1] for item in sorted_items]

        # Create figure
        fig, ax = plt.subplots(figsize=(10, 6))

        colors = sns.color_palette("husl", len(labels))
        bars = ax.barh(labels, counts, color=colors)

        ax.set_xlabel("Number of Comments")
        ax.set_ylabel("Stakeholder Type")
        ax.set_title("Comment Distribution by Stakeholder Type")

        # Add value labels
        for bar, count in zip(bars, counts):
            ax.annotate(
                f"{count:,}",
                xy=(bar.get_width() + max(counts) * 0.01, bar.get_y() + bar.get_height() / 2),
                va="center", fontsize=9
            )

        ax.invert_yaxis()
        plt.tight_layout()
        return self._save_figure(fig, name)

    def frame_distribution(
        self,
        frame_data: Dict,
        name: str = "four_frame_distribution",
    ) -> Tuple[Path, Path]:
        """
        Create visualization of four-frame distribution.

        Args:
            frame_data: Frame analysis results
            name: Output filename

        Returns:
            Tuple of (png_path, pdf_path)
        """
        frame_counts = frame_data.get("frame_counts", {})
        frame_names = {
            "body_self": "Body/Self",
            "product_drug": "Product/Drug",
            "treatment_therapy": "Treatment/Therapy",
            "economic_access": "Economic/Access",
        }

        labels = [frame_names.get(k, k) for k in frame_counts.keys()]
        counts = list(frame_counts.values())

        fig, ax = plt.subplots(figsize=(10, 6))

        colors = ["#e74c3c", "#3498db", "#2ecc71", "#f39c12"]
        bars = ax.bar(labels, counts, color=colors[:len(labels)])

        ax.set_xlabel("Rhetorical Frame")
        ax.set_ylabel("Number of Comments")
        ax.set_title("Distribution of Rhetorical Frames in FDA Comments")

        # Add value labels
        for bar, count in zip(bars, counts):
            ax.annotate(
                f"{count:,}",
                xy=(bar.get_x() + bar.get_width() / 2, bar.get_height()),
                ha="center", va="bottom", fontsize=10
            )

        plt.tight_layout()
        return self._save_figure(fig, name)

    def possessive_comparison(
        self,
        comparison_data: Dict,
        name: str = "possessive_comparison",
    ) -> Tuple[Path, Path]:
        """
        Create comparison chart of possessive language usage.

        Args:
            comparison_data: Possessive comparison results
            name: Output filename

        Returns:
            Tuple of (png_path, pdf_path)
        """
        personal = comparison_data.get("personal_narratives", {})
        technical = comparison_data.get("technical_documents", {})

        fig, axes = plt.subplots(1, 2, figsize=(12, 5))

        # Average per document comparison
        ax1 = axes[0]
        categories = ["Personal\nNarratives", "Technical\nDocuments"]
        avgs = [
            personal.get("avg_per_doc", 0),
            technical.get("avg_per_doc", 0),
        ]
        colors = ["#e74c3c", "#3498db"]

        bars = ax1.bar(categories, avgs, color=colors)
        ax1.set_ylabel("Average Possessives per Document")
        ax1.set_title("Possessive Language Density by Comment Type")

        for bar, avg in zip(bars, avgs):
            ax1.annotate(
                f"{avg:.1f}",
                xy=(bar.get_x() + bar.get_width() / 2, bar.get_height()),
                ha="center", va="bottom", fontsize=12
            )

        # Category breakdown
        ax2 = axes[1]
        personal_cats = personal.get("categories", {})
        technical_cats = technical.get("categories", {})

        all_cats = sorted(set(list(personal_cats.keys()) + list(technical_cats.keys())))

        x = np.arange(len(all_cats))
        width = 0.35

        personal_vals = [personal_cats.get(c, 0) for c in all_cats]
        technical_vals = [technical_cats.get(c, 0) for c in all_cats]

        ax2.bar(x - width/2, personal_vals, width, label="Personal", color="#e74c3c")
        ax2.bar(x + width/2, technical_vals, width, label="Technical", color="#3498db")

        ax2.set_ylabel("Count")
        ax2.set_title("Possessive Object Categories")
        ax2.set_xticks(x)
        ax2.set_xticklabels(all_cats, rotation=45, ha="right")
        ax2.legend()

        plt.tight_layout()
        return self._save_figure(fig, name)

    def duplicate_analysis(
        self,
        duplicate_data: Dict,
        name: str = "duplicate_analysis",
    ) -> Tuple[Path, Path]:
        """
        Visualize duplicate/unique comment breakdown.

        Args:
            duplicate_data: Duplicate analysis results
            name: Output filename

        Returns:
            Tuple of (png_path, pdf_path)
        """
        total = duplicate_data.get("total_comments", 0)
        unique = duplicate_data.get("unique_comments", 0)
        in_groups = duplicate_data.get("comments_in_groups", 0)

        fig, axes = plt.subplots(1, 2, figsize=(12, 5))

        # Pie chart
        ax1 = axes[0]
        sizes = [unique, in_groups]
        labels = ["Unique Arguments", "Form Letters"]
        colors = ["#2ecc71", "#e74c3c"]
        explode = (0.05, 0)

        ax1.pie(sizes, explode=explode, labels=labels, colors=colors,
               autopct="%1.1f%%", startangle=90)
        ax1.set_title("Unique vs. Form Letter Comments")

        # Group size distribution
        ax2 = axes[1]
        groups = duplicate_data.get("groups", [])
        if groups:
            sizes = [g["size"] for g in groups]
            ax2.hist(sizes, bins=20, color="#3498db", edgecolor="black", alpha=0.7)
            ax2.set_xlabel("Group Size (# of Similar Comments)")
            ax2.set_ylabel("Number of Groups")
            ax2.set_title("Form Letter Group Size Distribution")
            ax2.axvline(np.mean(sizes), color="red", linestyle="--",
                       label=f"Mean: {np.mean(sizes):.1f}")
            ax2.legend()
        else:
            ax2.text(0.5, 0.5, "No duplicate groups found",
                    ha="center", va="center", transform=ax2.transAxes)

        plt.tight_layout()
        return self._save_figure(fig, name)

    def citation_heatmap(
        self,
        citation_data: Dict,
        name: str = "citation_heatmap",
    ) -> Tuple[Path, Path]:
        """
        Create heatmap of citations by stakeholder type.

        Args:
            citation_data: Citation analysis results
            name: Output filename

        Returns:
            Tuple of (png_path, pdf_path)
        """
        by_stakeholder = citation_data.get("by_stakeholder", {})

        if not by_stakeholder:
            logger.warning("No stakeholder citation data available")
            fig, ax = plt.subplots(figsize=(8, 6))
            ax.text(0.5, 0.5, "No data available", ha="center", va="center")
            return self._save_figure(fig, name)

        # Create DataFrame
        df = pd.DataFrame(by_stakeholder).T.fillna(0)

        fig, ax = plt.subplots(figsize=(10, 8))

        sns.heatmap(df, annot=True, fmt=".0f", cmap="YlOrRd", ax=ax)
        ax.set_title("Citation Types by Stakeholder Category")
        ax.set_xlabel("Citation Type")
        ax.set_ylabel("Stakeholder Category")

        plt.tight_layout()
        return self._save_figure(fig, name)

    def generate_all_charts(
        self,
        comments: Optional[List[Dict]] = None,
    ) -> Dict[str, Tuple[Path, Path]]:
        """
        Generate all available charts from analysis outputs.

        Args:
            comments: List of comment dicts

        Returns:
            Dict of chart names to file paths
        """
        if comments is None:
            comments = self.data_loader.load_comments_json()

        output_files = {}

        # Comment type distribution
        if comments:
            paths = self.comment_type_distribution(comments)
            output_files["comment_type_distribution"] = paths

        # Load processed data files if available
        processed = config.PROCESSED_DIR

        # Frame distribution
        frame_path = processed / "four_frame_distribution.json"
        if frame_path.exists():
            with open(frame_path) as f:
                frame_data = json.load(f)
            paths = self.frame_distribution(frame_data)
            output_files["frame_distribution"] = paths

        # Possessive comparison
        poss_path = processed / "possessive_comparison.json"
        if poss_path.exists():
            with open(poss_path) as f:
                poss_data = json.load(f)
            paths = self.possessive_comparison(poss_data)
            output_files["possessive_comparison"] = paths

        # Duplicate analysis
        dup_path = processed / "duplicate_analysis.json"
        if dup_path.exists():
            with open(dup_path) as f:
                dup_data = json.load(f)
            paths = self.duplicate_analysis(dup_data)
            output_files["duplicate_analysis"] = paths

        # Citation heatmap
        cite_path = processed / "citation_summary.json"
        if cite_path.exists():
            with open(cite_path) as f:
                cite_data = json.load(f)
            paths = self.citation_heatmap(cite_data)
            output_files["citation_heatmap"] = paths

        logger.info(f"Generated {len(output_files)} chart sets")
        return output_files


def main():
    """Main entry point for chart generator."""
    import argparse

    parser = argparse.ArgumentParser(description="Generate analysis charts")
    parser.add_argument("--input", help="Input JSON file")
    parser.add_argument("--all", action="store_true", help="Generate all available charts")
    parser.add_argument("--chart", choices=[
        "comment_type", "stakeholder", "frames", "possessive", "duplicates", "citations"
    ], help="Generate specific chart")

    args = parser.parse_args()

    generator = ChartGenerator()

    if args.all:
        input_path = Path(args.input) if args.input else None
        comments = generator.data_loader.load_comments_json(input_path)
        output_files = generator.generate_all_charts(comments)
        print(f"\nGenerated {len(output_files)} chart sets:")
        for name, (png, pdf) in output_files.items():
            print(f"  - {name}: {png}")
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
