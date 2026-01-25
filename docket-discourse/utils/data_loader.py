"""
Common data loading functions for the docket-discourse analysis suite.
"""
import json
import csv
from pathlib import Path
from typing import List, Dict, Optional, Generator, Union
import logging

from . import config

logger = logging.getLogger(__name__)


class DataLoader:
    """Load and manage comment data from various sources."""

    def __init__(self):
        """Initialize data loader with default paths."""
        self.raw_dir = config.RAW_DIR
        self.processed_dir = config.PROCESSED_DIR

    def load_comments_json(
        self, filepath: Optional[Path] = None
    ) -> List[Dict]:
        """
        Load comments from JSON file.

        Args:
            filepath: Path to JSON file (defaults to raw/comments.json)

        Returns:
            List of comment dictionaries
        """
        if filepath is None:
            filepath = self.raw_dir / "comments.json"

        try:
            with open(filepath, "r", encoding="utf-8") as f:
                data = json.load(f)

            # Handle both list and dict with 'comments' key
            if isinstance(data, list):
                return data
            elif isinstance(data, dict) and "comments" in data:
                return data["comments"]
            else:
                logger.warning(f"Unexpected JSON structure in {filepath}")
                return []

        except FileNotFoundError:
            logger.error(f"Comments file not found: {filepath}")
            return []
        except json.JSONDecodeError as e:
            logger.error(f"JSON decode error in {filepath}: {e}")
            return []

    def load_comments_csv(
        self, filepath: Optional[Path] = None
    ) -> List[Dict]:
        """
        Load comments from CSV file.

        Args:
            filepath: Path to CSV file (defaults to raw/comments.csv)

        Returns:
            List of comment dictionaries
        """
        if filepath is None:
            filepath = self.raw_dir / "comments.csv"

        comments = []
        try:
            with open(filepath, "r", encoding="utf-8", newline="") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    comments.append(dict(row))
            return comments

        except FileNotFoundError:
            logger.error(f"CSV file not found: {filepath}")
            return []
        except Exception as e:
            logger.error(f"Error reading CSV {filepath}: {e}")
            return []

    def stream_comments_json(
        self, filepath: Optional[Path] = None, batch_size: int = 100
    ) -> Generator[List[Dict], None, None]:
        """
        Stream comments from JSON file in batches (memory efficient).

        Args:
            filepath: Path to JSON file
            batch_size: Number of comments per batch

        Yields:
            Batches of comment dictionaries
        """
        comments = self.load_comments_json(filepath)
        for i in range(0, len(comments), batch_size):
            yield comments[i : i + batch_size]

    def load_by_type(
        self, comment_type: str, filepath: Optional[Path] = None
    ) -> List[Dict]:
        """
        Load comments filtered by classification type.

        Args:
            comment_type: One of 'personal_narrative', 'technical_document', 'organizational'
            filepath: Path to JSON file

        Returns:
            Filtered list of comments
        """
        comments = self.load_comments_json(filepath)
        return [
            c for c in comments
            if c.get("classification", {}).get("type") == comment_type
        ]

    def load_technical_terms(self) -> Dict:
        """Load technical terms dictionary."""
        filepath = config.DICTIONARIES_DIR / "technical_terms.json"
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            logger.warning("Technical terms dictionary not found or invalid")
            return {}

    def load_stakeholder_keywords(self) -> Dict:
        """Load stakeholder keywords dictionary."""
        filepath = config.DICTIONARIES_DIR / "stakeholder_keywords.json"
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            logger.warning("Stakeholder keywords dictionary not found or invalid")
            return {}

    def save_json(
        self, data: Union[List, Dict], filepath: Path, indent: int = 2
    ) -> bool:
        """
        Save data to JSON file.

        Args:
            data: Data to save
            filepath: Output path
            indent: JSON indentation

        Returns:
            True if successful
        """
        try:
            filepath.parent.mkdir(parents=True, exist_ok=True)
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=indent, ensure_ascii=False)
            logger.info(f"Saved JSON to {filepath}")
            return True
        except Exception as e:
            logger.error(f"Error saving JSON to {filepath}: {e}")
            return False

    def save_csv(
        self, data: List[Dict], filepath: Path, fieldnames: Optional[List[str]] = None
    ) -> bool:
        """
        Save data to CSV file.

        Args:
            data: List of dictionaries to save
            filepath: Output path
            fieldnames: Column names (auto-detected if not provided)

        Returns:
            True if successful
        """
        if not data:
            logger.warning("No data to save to CSV")
            return False

        try:
            filepath.parent.mkdir(parents=True, exist_ok=True)

            if fieldnames is None:
                # Collect all keys from all rows
                all_keys = set()
                for row in data:
                    all_keys.update(row.keys())
                fieldnames = sorted(all_keys)

            with open(filepath, "w", encoding="utf-8", newline="") as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
                writer.writeheader()
                writer.writerows(data)

            logger.info(f"Saved CSV to {filepath}")
            return True
        except Exception as e:
            logger.error(f"Error saving CSV to {filepath}: {e}")
            return False

    def save_searchable_text(
        self, comments: List[Dict], filepath: Path, text_field: str = "comment_text"
    ) -> bool:
        """
        Save comments as searchable plain text file.

        Each comment is separated by a delimiter with its ID for reference.

        Args:
            comments: List of comment dictionaries
            filepath: Output path
            text_field: Key containing the comment text

        Returns:
            True if successful
        """
        try:
            filepath.parent.mkdir(parents=True, exist_ok=True)

            with open(filepath, "w", encoding="utf-8") as f:
                for comment in comments:
                    comment_id = comment.get("id", comment.get("document_id", "unknown"))
                    text = comment.get(text_field, "")
                    posted_date = comment.get("posted_date", "")

                    f.write(f"{'=' * 80}\n")
                    f.write(f"COMMENT ID: {comment_id}\n")
                    if posted_date:
                        f.write(f"DATE: {posted_date}\n")
                    f.write(f"{'=' * 80}\n\n")
                    f.write(f"{text}\n\n")

            logger.info(f"Saved searchable text to {filepath}")
            return True
        except Exception as e:
            logger.error(f"Error saving text to {filepath}: {e}")
            return False

    def load_checkpoint(self, checkpoint_file: Path) -> Dict:
        """Load scraping checkpoint for resume functionality."""
        try:
            with open(checkpoint_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return {"last_page": 0, "comments_processed": 0, "comment_ids": []}

    def save_checkpoint(self, checkpoint_data: Dict, checkpoint_file: Path) -> bool:
        """Save scraping checkpoint."""
        return self.save_json(checkpoint_data, checkpoint_file)


# Convenience functions
def load_comments(filepath: Optional[Path] = None) -> List[Dict]:
    """Load comments from default JSON file."""
    loader = DataLoader()
    return loader.load_comments_json(filepath)


def load_comments_by_type(comment_type: str) -> List[Dict]:
    """Load comments filtered by type."""
    loader = DataLoader()
    return loader.load_by_type(comment_type)


def save_results(data: Union[List, Dict], filename: str, output_dir: Optional[Path] = None) -> bool:
    """Save analysis results to processed directory."""
    loader = DataLoader()
    if output_dir is None:
        output_dir = config.PROCESSED_DIR

    filepath = output_dir / filename
    if filename.endswith(".json"):
        return loader.save_json(data, filepath)
    elif filename.endswith(".csv") and isinstance(data, list):
        return loader.save_csv(data, filepath)
    else:
        logger.error(f"Unsupported file format: {filename}")
        return False
