"""
Manual Attachment Fetcher

Attempts to recover attachments for comments that reference an attachment
but lack metadata in the regulations.gov API response.
"""
from __future__ import annotations

import io
import logging
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional

import requests

try:
    import PyPDF2

    PDF_SUPPORT = True
except ImportError:  # pragma: no cover - optional dependency
    PDF_SUPPORT = False

import sys

sys.path.insert(0, str(Path(__file__).parent.parent))

from utils import config
from utils.data_loader import DataLoader


logger = logging.getLogger(__name__)


@dataclass
class DownloadResult:
    """Container for recovered attachment content."""

    url: str
    extension: str
    content: bytes


class AttachmentFetcher:
    """
    Fetch attachments from downloads.regulations.gov when API metadata is missing.
    """

    KEYWORD_PATTERNS = [
        re.compile(r"\bsee\s+attach", re.IGNORECASE),
        re.compile(r"\battachment[s]?\b", re.IGNORECASE),
        re.compile(r"\bsee\s+enclosure", re.IGNORECASE),
        re.compile(r"\benclosed\b", re.IGNORECASE),
    ]

    EXTENSIONS = ["pdf", "docx", "doc", "txt"]

    def __init__(self, max_per_comment: int = 3):
        self.data_loader = DataLoader()
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        })
        self.max_per_comment = max_per_comment
        self.output_dir = config.RAW_DIR / "manual_attachments"
        self.output_dir.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    def run(self, comments: Optional[List[Dict]] = None) -> Dict:
        """
        Attempt to download missing attachments for all candidate comments.
        """
        if comments is None:
            comments = self.data_loader.load_comments_json()

        if not comments:
            logger.warning("No comments available for attachment recovery.")
            return {"processed_comments": 0, "attachments_downloaded": 0}

        candidates = [
            comment for comment in comments if self._needs_manual_attachment(comment)
        ]
        logger.info(
            "Manual attachment fetcher evaluating %d candidates", len(candidates)
        )

        updated = False
        total_downloaded = 0

        for comment in candidates:
            try:
                recovered = self._process_comment(comment)
                total_downloaded += recovered
                if recovered:
                    updated = True
                    logger.info(
                        "Recovered %d attachment(s) for %s",
                        recovered,
                        comment.get("id", ""),
                    )
            except Exception as exc:  # pragma: no cover - best effort
                logger.error("Failed to recover attachments for %s: %s", comment, exc)

        if updated:
            logger.info("Saving updated comments.json with manual attachments")
            self.data_loader.save_json(comments, config.RAW_DIR / "comments.json")

        summary = {
            "processed_comments": len(candidates),
            "attachments_downloaded": total_downloaded,
            "updated_comments_file": updated,
        }
        report_path = config.PROCESSED_DIR / "manual_attachment_report.json"
        self.data_loader.save_json(summary, report_path)
        logger.info("Manual attachment report written to %s", report_path)

        return summary

    # ------------------------------------------------------------------
    def _needs_manual_attachment(self, comment: Dict) -> bool:
        """Return True if a comment references attachments but none were saved."""
        if comment.get("has_attachments"):
            return False

        text = (comment.get("full_text") or comment.get("comment_text") or "").strip()

        # Blank comment bodies often mean the attachment holds all content.
        if not text:
            return True

        return any(pattern.search(text) for pattern in self.KEYWORD_PATTERNS)

    def _process_comment(self, comment: Dict) -> int:
        """Attempt to download up to N attachments for a single comment."""
        comment_id = comment.get("id", "")
        recovered = 0
        comment_dir = self.output_dir / comment_id
        comment_dir.mkdir(parents=True, exist_ok=True)

        for attachment_index in range(1, self.max_per_comment + 1):
            if self._existing_attachment_file(comment_dir, attachment_index):
                continue

            download = self._download_attachment(comment_id, attachment_index)
            if not download:
                break  # attachments are sequential; stop at first miss

            file_path = (
                comment_dir / f"attachment_{attachment_index}.{download.extension}"
            )
            file_path.write_bytes(download.content)
            recovered += 1

            attachment_info = self._build_attachment_metadata(
                comment_id, attachment_index, download, file_path
            )
            comment.setdefault("attachments", []).append(attachment_info)
            comment["has_attachments"] = True

            extracted_text = attachment_info.get("pdf_extraction", {}).get("text")
            if extracted_text:
                body = comment.get("full_text") or comment.get("comment_text") or ""
                comment["full_text"] = (
                    body + "\n\n[MANUAL ATTACHMENT TEXT]\n" + extracted_text
                )

        return recovered

    def _existing_attachment_file(self, directory: Path, index: int) -> Optional[Path]:
        """Check if an attachment file already exists locally."""
        for ext in self.EXTENSIONS:
            candidate = directory / f"attachment_{index}.{ext}"
            if candidate.exists():
                return candidate
        return None

    def _download_attachment(
        self, comment_id: str, attachment_index: int
    ) -> Optional[DownloadResult]:
        """Try downloading attachment_{index} using known extensions."""
        base_url = f"https://downloads.regulations.gov/{comment_id}/attachment_{attachment_index}"

        for ext in self.EXTENSIONS:
            url = f"{base_url}.{ext}"
            try:
                response = self.session.get(url, timeout=30)
            except requests.RequestException:  # pragma: no cover - network
                continue

            if response.status_code == 200 and response.content:
                return DownloadResult(url=url, extension=ext, content=response.content)

        return None

    def _build_attachment_metadata(
        self,
        comment_id: str,
        attachment_index: int,
        download: DownloadResult,
        file_path: Path,
    ) -> Dict:
        """Create attachment metadata structure similar to scraper output."""
        metadata = {
            "id": f"{comment_id}_manual_{attachment_index}",
            "title": f"Manual Attachment {attachment_index}",
            "format": [
                {
                    "format": download.extension,
                    "fileUrl": download.url,
                }
            ],
            "manual_downloaded": True,
            "file_path": str(file_path.relative_to(config.PROJECT_ROOT)),
        }

        if download.extension == "pdf":
            metadata["pdf_extraction"] = self._extract_pdf_text(download.content)

        return metadata

    def _extract_pdf_text(self, content: bytes) -> Dict:
        """Extract text from a PDF attachment."""
        if not PDF_SUPPORT:
            return {
                "text": "",
                "flagged_for_review": True,
                "error": "PyPDF2 not installed",
                "extraction_method": None,
            }

        try:
            reader = PyPDF2.PdfReader(io.BytesIO(content))
            text_parts = []
            for page in reader.pages:
                page_text = page.extract_text()
                if page_text:
                    text_parts.append(page_text)

            text = " ".join(text_parts)
            return {
                "text": text,
                "flagged_for_review": True,
                "extraction_method": "PyPDF2",
                "page_count": len(reader.pages),
                "char_count": len(text),
            }
        except Exception as exc:  # pragma: no cover - best effort
            return {
                "text": "",
                "flagged_for_review": True,
                "error": str(exc),
                "extraction_method": "PyPDF2",
            }


def main():
    """CLI hook."""
    logging.basicConfig(level=logging.INFO, format=config.LOG_FORMAT)
    AttachmentFetcher().run()


if __name__ == "__main__":
    main()
