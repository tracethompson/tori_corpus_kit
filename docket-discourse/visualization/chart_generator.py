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

        # Load processed data files if available
        processed = config.PROCESSED_DIR

        # Frame distribution
        frame_path = processed / "four_frame_distribution.json"
        if frame_path.exists():
            with open(frame_path) as f:
                frame_data = json.load(f)
            paths = self.frame_distribution(frame_data)
            output_files["frame_distribution"] = paths

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
        "frames", "duplicates", "citations"
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
