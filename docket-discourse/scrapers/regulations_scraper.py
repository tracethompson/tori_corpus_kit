"""
Tool 1: Regulations.gov API Scraper

Fetches public comments from FDA docket FDA-2015-D-3719 via the regulations.gov API.
Handles pagination, attachments, PDF extraction, and real-time classification.
"""
import os
import io
import time
import json
import logging
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from datetime import datetime

import requests
from tqdm import tqdm

try:
    import PyPDF2
    PDF_SUPPORT = True
except ImportError:
    PDF_SUPPORT = False

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from utils import config
from utils.comment_classifier import CommentClassifier
from utils.data_loader import DataLoader

logging.basicConfig(level=logging.INFO, format=config.LOG_FORMAT)
logger = logging.getLogger(__name__)


class RegulationsScraper:
    """Scrape comments from regulations.gov API."""

    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize the scraper.

        Args:
            api_key: regulations.gov API key (or use env var)
        """
        self.api_key = api_key or config.REGULATIONS_GOV_API_KEY
        if not self.api_key:
            raise ValueError(
                "API key required. Set REGULATIONS_GOV_API_KEY environment variable "
                "or pass api_key parameter."
            )

        self.base_url = config.REGULATIONS_API_BASE
        self.rate_limit_delay = config.RATE_LIMIT_DELAY
        self.classifier = CommentClassifier()
        self.data_loader = DataLoader()

        # Statistics
        self.stats = {
            "total_fetched": 0,
            "personal_narratives": 0,
            "technical_documents": 0,
            "organizational": 0,
            "pdfs_processed": 0,
            "pdfs_flagged": 0,
            "errors": 0,
        }

    def _make_request(
        self, endpoint: str, params: Optional[Dict] = None
    ) -> Optional[Dict]:
        """Make API request with rate limiting and error handling."""
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
            self.stats["errors"] += 1
            return None

        except requests.exceptions.RequestException as e:
            logger.error(f"Request error: {e}")
            self.stats["errors"] += 1
            return None

    def fetch_comments_list(
        self,
        docket_id: str = config.DOCKET_ID,
        page_size: int = 250,
        start_page: int = 1,
    ) -> List[Dict]:
        """
        Fetch paginated list of comment IDs and metadata.

        Args:
            docket_id: FDA docket ID
            page_size: Comments per page (max 250)
            start_page: Page to start from (for resume)

        Returns:
            List of comment metadata dicts
        """
        all_comments = []
        page = start_page
        total_pages = None

        logger.info(f"Fetching comments list for docket {docket_id}")

        while True:
            params = {
                "filter[docketId]": docket_id,
                "page[size]": page_size,
                "page[number]": page,
                "sort": "postedDate",
            }

            result = self._make_request("/comments", params)
            if not result:
                break

            data = result.get("data", [])
            if not data:
                break

            all_comments.extend(data)

            # Get pagination info
            meta = result.get("meta", {})
            if total_pages is None:
                total_pages = meta.get("totalPages", 1)
                total_elements = meta.get("totalElements", len(data))
                logger.info(f"Total comments: {total_elements}, pages: {total_pages}")

            logger.info(f"Fetched page {page}/{total_pages} ({len(data)} comments)")

            if page >= total_pages:
                break

            page += 1

        logger.info(f"Total comment metadata fetched: {len(all_comments)}")
        return all_comments

    def fetch_comment_detail(self, comment_id: str) -> Optional[Dict]:
        """
        Fetch full details for a single comment.

        Args:
            comment_id: Comment document ID

        Returns:
            Full comment data including text and attachments
        """
        # Include attachments in the response
        result = self._make_request(f"/comments/{comment_id}", {"include": "attachments"})
        if not result:
            return None

        # Return both data and included (attachments) sections
        return {
            "data": result.get("data", {}),
            "included": result.get("included", []),
        }

    def extract_pdf_text(self, pdf_url: str) -> Dict:
        """
        Extract text from PDF attachment.

        Args:
            pdf_url: URL to PDF file

        Returns:
            Dict with extracted text and metadata
        """
        if not PDF_SUPPORT:
            return {
                "text": "",
                "flagged_for_review": True,
                "error": "PyPDF2 not installed",
                "extraction_method": None,
            }

        try:
            response = requests.get(pdf_url, timeout=60)
            response.raise_for_status()

            reader = PyPDF2.PdfReader(io.BytesIO(response.content))
            text_parts = []

            for page in reader.pages:
                page_text = page.extract_text()
                if page_text:
                    text_parts.append(page_text)

            text = " ".join(text_parts)
            self.stats["pdfs_processed"] += 1

            return {
                "text": text,
                "flagged_for_review": True,  # Always flag PDFs for manual review
                "extraction_method": "PyPDF2",
                "page_count": len(reader.pages),
                "char_count": len(text),
            }

        except Exception as e:
            self.stats["pdfs_flagged"] += 1
            logger.warning(f"PDF extraction error: {e}")
            return {
                "text": "",
                "flagged_for_review": True,
                "error": str(e),
                "extraction_method": "PyPDF2",
            }

    def process_comment(self, comment_data: Dict) -> Dict:
        """
        Process a single comment: extract text, handle attachments, classify.

        Args:
            comment_data: Raw API response for comment

        Returns:
            Processed comment dict
        """
        attributes = comment_data.get("attributes", {})

        # Extract basic info
        comment_id = comment_data.get("id", "")
        comment_text = attributes.get("comment", "") or ""
        posted_date = attributes.get("postedDate", "")
        title = attributes.get("title", "")
        submitter_name = attributes.get("firstName", "")
        if attributes.get("lastName"):
            submitter_name += f" {attributes.get('lastName')}"

        # Check for attachments
        attachments = []
        attachment_texts = []
        relationships = comment_data.get("relationships", {})

        if relationships.get("attachments", {}).get("data"):
            for attachment in relationships["attachments"]["data"]:
                att_id = attachment.get("id", "")
                # Fetch attachment details
                att_result = self._make_request(f"/documents/{att_id}")
                if att_result:
                    att_data = att_result.get("data", {})
                    att_attrs = att_data.get("attributes", {})

                    att_info = {
                        "id": att_id,
                        "title": att_attrs.get("title", ""),
                        "format": att_attrs.get("fileFormats", []),
                    }

                    # Extract PDF text if available
                    for fmt in att_attrs.get("fileFormats", []):
                        if fmt.get("format") == "pdf":
                            pdf_result = self.extract_pdf_text(fmt.get("fileUrl", ""))
                            att_info["pdf_extraction"] = pdf_result
                            if pdf_result.get("text"):
                                attachment_texts.append(pdf_result["text"])

                    attachments.append(att_info)

        # Combine comment text with attachment text
        full_text = comment_text
        if attachment_texts:
            full_text += "\n\n[ATTACHMENT TEXT]\n" + "\n".join(attachment_texts)

        # Calculate word count
        word_count = len(full_text.split()) if full_text else 0

        # Classify comment
        classification = self.classifier.classify_comment_type(full_text, word_count)

        # Update stats
        self.stats["total_fetched"] += 1
        comment_type = classification.get("type", "unknown")
        if comment_type == "personal_narrative":
            self.stats["personal_narratives"] += 1
        elif comment_type == "technical_document":
            self.stats["technical_documents"] += 1
        elif comment_type == "organizational":
            self.stats["organizational"] += 1

        return {
            "id": comment_id,
            "document_id": comment_id,
            "title": title,
            "submitter_name": submitter_name,
            "posted_date": posted_date,
            "comment_text": comment_text,
            "full_text": full_text,
            "word_count": word_count,
            "has_attachments": len(attachments) > 0,
            "attachments": attachments,
            "classification": classification,
            "raw_attributes": attributes,
        }

    def scrape_docket(
        self,
        docket_id: str = config.DOCKET_ID,
        resume: bool = True,
        limit: Optional[int] = None,
    ) -> List[Dict]:
        """
        Full scrape of all comments in a docket.

        Args:
            docket_id: FDA docket ID
            resume: Whether to resume from checkpoint
            limit: Maximum comments to fetch (for testing)

        Returns:
            List of processed comments
        """
        config.ensure_directories()

        checkpoint_file = config.RAW_DIR / f"{docket_id}_checkpoint.json"
        output_file = config.RAW_DIR / "comments.json"

        # Load checkpoint if resuming
        processed_comments = []
        processed_ids = set()

        if resume and checkpoint_file.exists():
            checkpoint = self.data_loader.load_checkpoint(checkpoint_file)
            logger.info(f"Resuming from checkpoint: {checkpoint['comments_processed']} comments")
            processed_ids = set(checkpoint.get("comment_ids", []))

            # Load existing comments
            if output_file.exists():
                processed_comments = self.data_loader.load_comments_json(output_file)

        # Fetch comment list
        comment_list = self.fetch_comments_list(docket_id)

        # Filter out already-processed comments
        comments_to_process = [c for c in comment_list if c.get("id", "") not in processed_ids]

        # Apply limit to NEW comments to fetch
        if limit:
            comments_to_process = comments_to_process[:limit]

        logger.info(f"Processing {len(comments_to_process)} new comments...")

        # Process each comment
        for i, comment_meta in enumerate(tqdm(comments_to_process, desc="Fetching comments")):
            comment_id = comment_meta.get("id", "")

            # Fetch and process full comment
            detail = self.fetch_comment_detail(comment_id)
            if detail:
                processed = self.process_comment(detail["data"])
                processed_comments.append(processed)
                processed_ids.add(comment_id)

            # Save checkpoint periodically
            if (i + 1) % config.CHECKPOINT_INTERVAL == 0:
                self._save_checkpoint(
                    checkpoint_file, output_file,
                    processed_comments, processed_ids, len(processed_comments)
                )

        # Final save
        self._save_checkpoint(
            checkpoint_file, output_file,
            processed_comments, processed_ids, len(processed_comments)
        )

        logger.info(f"Scraping complete. Stats: {self.stats}")
        return processed_comments

    def _save_checkpoint(
        self,
        checkpoint_file: Path,
        output_file: Path,
        comments: List[Dict],
        comment_ids: set,
        page: int,
    ):
        """Save progress checkpoint and current data."""
        checkpoint = {
            "last_page": page,
            "comments_processed": len(comments),
            "comment_ids": list(comment_ids),
            "timestamp": datetime.now().isoformat(),
            "stats": self.stats,
        }
        self.data_loader.save_checkpoint(checkpoint, checkpoint_file)
        self.data_loader.save_json(comments, output_file)
        logger.info(f"Checkpoint saved: {len(comments)} comments")

    def export_searchable_text(
        self,
        comments: Optional[List[Dict]] = None,
        output_dir: Optional[Path] = None,
    ) -> Dict[str, Path]:
        """
        Export comments as searchable text files by type.

        Args:
            comments: List of comments (or load from file)
            output_dir: Output directory

        Returns:
            Dict of output file paths
        """
        if comments is None:
            comments = self.data_loader.load_comments_json()

        if output_dir is None:
            output_dir = config.RAW_DIR

        output_files = {}

        # All comments
        all_path = output_dir / "comments_searchable_ALL.txt"
        self.data_loader.save_searchable_text(comments, all_path, "full_text")
        output_files["all"] = all_path

        # By type
        type_mapping = {
            "personal_narratives": "personal_narrative",
            "technical_documents": "technical_document",
            "organizational": "organizational",
        }

        for filename_part, type_value in type_mapping.items():
            filtered = [
                c for c in comments
                if c.get("classification", {}).get("type") == type_value
            ]
            path = output_dir / f"comments_searchable_{filename_part}.txt"
            self.data_loader.save_searchable_text(filtered, path, "full_text")
            output_files[filename_part] = path
            logger.info(f"Exported {len(filtered)} {filename_part}")

        return output_files

    def export_csv(
        self,
        comments: Optional[List[Dict]] = None,
        output_path: Optional[Path] = None,
    ) -> Path:
        """
        Export comments to CSV with classification columns.

        Args:
            comments: List of comments (or load from file)
            output_path: Output file path

        Returns:
            Output file path
        """
        if comments is None:
            comments = self.data_loader.load_comments_json()

        if output_path is None:
            output_path = config.RAW_DIR / "comments.csv"

        # Flatten for CSV
        csv_data = []
        for comment in comments:
            classification = comment.get("classification", {})
            csv_data.append({
                "id": comment.get("id", ""),
                "posted_date": comment.get("posted_date", ""),
                "submitter_name": comment.get("submitter_name", ""),
                "word_count": comment.get("word_count", 0),
                "has_attachments": comment.get("has_attachments", False),
                "comment_type": classification.get("type", ""),
                "type_confidence": classification.get("confidence", 0),
                "technical_density": classification.get("signals", {}).get("technical_density", 0),
                "possessive_count": classification.get("signals", {}).get("possessive_count", 0),
                "comment_text": comment.get("comment_text", "")[:1000],  # Truncate for CSV
            })

        self.data_loader.save_csv(csv_data, output_path)
        logger.info(f"Exported {len(csv_data)} comments to {output_path}")
        return output_path


def main():
    """Main entry point for regulations scraper."""
    import argparse

    parser = argparse.ArgumentParser(description="Scrape FDA docket comments from regulations.gov")
    parser.add_argument("--docket", default=config.DOCKET_ID, help="Docket ID to scrape")
    parser.add_argument("--limit", type=int, help="Limit number of comments (for testing)")
    parser.add_argument("--no-resume", action="store_true", help="Start fresh, don't resume")
    parser.add_argument("--export-only", action="store_true", help="Only export existing data")

    args = parser.parse_args()

    scraper = RegulationsScraper()

    if args.export_only:
        comments = scraper.data_loader.load_comments_json()
        if comments:
            scraper.export_searchable_text(comments)
            scraper.export_csv(comments)
        else:
            logger.error("No comments found to export")
    else:
        comments = scraper.scrape_docket(
            docket_id=args.docket,
            resume=not args.no_resume,
            limit=args.limit,
        )
        if comments:
            scraper.export_searchable_text(comments)
            scraper.export_csv(comments)


if __name__ == "__main__":
    main()
