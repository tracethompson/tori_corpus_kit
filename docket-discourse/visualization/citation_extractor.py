"""
Tool 8: Citation Extractor

Extract regulatory citations, legal references, and technical terms from FDA comments.
Includes CFR references, PHSA sections, and FDA guidance document mentions.
"""
import logging
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from collections import Counter, defaultdict
import re
import json

import pandas as pd

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from utils import config
from utils.data_loader import DataLoader

logging.basicConfig(level=logging.INFO, format=config.LOG_FORMAT)
logger = logging.getLogger(__name__)


class CitationExtractor:
    """Extract regulatory citations from FDA public comments."""

    def __init__(self):
        """Initialize citation extractor."""
        self.data_loader = DataLoader()

        # CFR citation patterns
        self.cfr_patterns = [
            r"21\s*C\.?F\.?R\.?\s*(?:Part\s*)?(\d+(?:\.\d+)?)",
            r"CFR\s*(?:Part\s*)?(\d+(?:\.\d+)?)",
            r"(?:Part|Section)\s*1271(?:\.(\d+))?",
        ]

        # PHSA section patterns
        self.phsa_patterns = [
            r"(?:Section|§)\s*(351|361)(?:\s*(?:of|under)\s*(?:the\s*)?(?:PHS|PHSA|Public\s*Health\s*Service\s*Act))?",
            r"(351|361)\s*(?:PHSA|PHS|product)",
            r"(?:PHS|PHSA)\s*(?:Section|§)?\s*(351|361)",
        ]

        # Guidance document patterns
        self.guidance_patterns = [
            r"(?:draft\s*)?guidance\s+(?:document\s+)?(?:for\s+)?(?:industry)?",
            r"same\s+surgical\s+procedure",
            r"minimal\s+manipulation",
            r"homologous\s+use",
        ]

        # Technical regulatory terms
        self.technical_terms = [
            "HCT/P", "HCTP", "biologics license", "BLA",
            "IND", "investigational", "premarket",
            "enforcement discretion", "establishment registration",
            "adverse event", "clinical trial",
        ]

    def extract_cfr_citations(self, text: str) -> List[Dict]:
        """
        Extract CFR citations from text.

        Args:
            text: Input text

        Returns:
            List of citation dicts with context
        """
        citations = []

        for pattern in self.cfr_patterns:
            for match in re.finditer(pattern, text, re.IGNORECASE):
                start = max(0, match.start() - 100)
                end = min(len(text), match.end() + 100)
                context = text[start:end]

                # Clean up context
                context = re.sub(r"\s+", " ", context).strip()
                if start > 0:
                    context = "..." + context
                if end < len(text):
                    context = context + "..."

                citations.append({
                    "type": "CFR",
                    "citation": match.group(0),
                    "section": match.group(1) if match.groups() else "",
                    "context": context,
                    "position": match.start(),
                })

        return citations

    def extract_phsa_citations(self, text: str) -> List[Dict]:
        """
        Extract PHSA section references from text.

        Args:
            text: Input text

        Returns:
            List of citation dicts with context
        """
        citations = []

        for pattern in self.phsa_patterns:
            for match in re.finditer(pattern, text, re.IGNORECASE):
                start = max(0, match.start() - 100)
                end = min(len(text), match.end() + 100)
                context = text[start:end]

                context = re.sub(r"\s+", " ", context).strip()
                if start > 0:
                    context = "..." + context
                if end < len(text):
                    context = context + "..."

                # Determine section number
                section = ""
                for group in match.groups():
                    if group in ["351", "361"]:
                        section = group
                        break

                citations.append({
                    "type": "PHSA",
                    "citation": match.group(0),
                    "section": section,
                    "context": context,
                    "position": match.start(),
                })

        return citations

    def extract_guidance_mentions(self, text: str) -> List[Dict]:
        """
        Extract FDA guidance document mentions.

        Args:
            text: Input text

        Returns:
            List of mention dicts with context
        """
        mentions = []
        text_lower = text.lower()

        for pattern in self.guidance_patterns:
            for match in re.finditer(pattern, text_lower, re.IGNORECASE):
                start = max(0, match.start() - 100)
                end = min(len(text), match.end() + 100)
                context = text[start:end]

                context = re.sub(r"\s+", " ", context).strip()
                if start > 0:
                    context = "..." + context
                if end < len(text):
                    context = context + "..."

                mentions.append({
                    "type": "guidance",
                    "phrase": match.group(0),
                    "context": context,
                    "position": match.start(),
                })

        return mentions

    def extract_technical_terms(self, text: str) -> List[Dict]:
        """
        Extract technical regulatory terms.

        Args:
            text: Input text

        Returns:
            List of term dicts with context
        """
        terms_found = []
        text_lower = text.lower()

        for term in self.technical_terms:
            term_lower = term.lower()
            for match in re.finditer(re.escape(term_lower), text_lower):
                start = max(0, match.start() - 75)
                end = min(len(text), match.end() + 75)
                context = text[start:end]

                context = re.sub(r"\s+", " ", context).strip()
                if start > 0:
                    context = "..." + context
                if end < len(text):
                    context = context + "..."

                terms_found.append({
                    "type": "technical_term",
                    "term": term,
                    "context": context,
                    "position": match.start(),
                })

        return terms_found

    def extract_all_citations(self, text: str) -> Dict[str, List]:
        """
        Extract all citation types from text.

        Args:
            text: Input text

        Returns:
            Dict of citation lists by type
        """
        return {
            "cfr": self.extract_cfr_citations(text),
            "phsa": self.extract_phsa_citations(text),
            "guidance": self.extract_guidance_mentions(text),
            "technical_terms": self.extract_technical_terms(text),
        }

    def analyze_corpus(
        self,
        comments: Optional[List[Dict]] = None,
        output_dir: Optional[Path] = None,
    ) -> Dict[str, Path]:
        """
        Extract citations from entire corpus.

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

        # Collect all citations
        all_citations = []
        citation_counts = defaultdict(Counter)
        by_stakeholder = defaultdict(lambda: defaultdict(int))

        for comment in comments:
            text = comment.get("full_text", comment.get("comment_text", ""))
            comment_id = comment.get("id", "")
            stakeholder = comment.get("stakeholder", {}).get("category", "unknown")
            comment_type = comment.get("classification", {}).get("type", "")

            citations = self.extract_all_citations(text)

            for citation_type, citation_list in citations.items():
                for citation in citation_list:
                    citation["comment_id"] = comment_id
                    citation["stakeholder"] = stakeholder
                    citation["comment_type"] = comment_type
                    all_citations.append(citation)

                    # Count by type
                    if citation_type == "cfr":
                        citation_counts["cfr"][citation.get("section", "")] += 1
                    elif citation_type == "phsa":
                        citation_counts["phsa"][citation.get("section", "")] += 1
                    elif citation_type == "technical_term":
                        citation_counts["terms"][citation.get("term", "")] += 1

                    # Count by stakeholder
                    by_stakeholder[stakeholder][citation_type] += 1

        # Export all citations
        if all_citations:
            df = pd.DataFrame(all_citations)
            path = output_dir / "citations_all.csv"
            df.to_csv(path, index=False)
            output_files["all_citations"] = path

        # Export by type
        for citation_type in ["cfr", "phsa", "guidance", "technical_terms"]:
            type_citations = [c for c in all_citations if c.get("type") == citation_type
                            or (citation_type == "technical_terms" and c.get("type") == "technical_term")]
            if type_citations:
                df = pd.DataFrame(type_citations)
                path = output_dir / f"citations_{citation_type}.csv"
                df.to_csv(path, index=False)
                output_files[f"citations_{citation_type}"] = path

        # Citation frequency summary
        summary = {
            "total_citations": len(all_citations),
            "cfr_sections": dict(citation_counts["cfr"].most_common(20)),
            "phsa_sections": dict(citation_counts["phsa"]),
            "technical_terms": dict(citation_counts["terms"].most_common(20)),
            "by_stakeholder": {k: dict(v) for k, v in by_stakeholder.items()},
        }

        path = output_dir / "citation_summary.json"
        self.data_loader.save_json(summary, path)
        output_files["summary"] = path

        # Cross-tabulation with stakeholder
        if all_citations:
            crosstab_data = []
            for stakeholder, type_counts in by_stakeholder.items():
                row = {"stakeholder": stakeholder}
                row.update(type_counts)
                crosstab_data.append(row)

            df = pd.DataFrame(crosstab_data)
            path = output_dir / "citations_by_stakeholder.csv"
            df.to_csv(path, index=False)
            output_files["by_stakeholder"] = path

        logger.info(f"Citation extraction complete. Found {len(all_citations)} citations.")
        return output_files

    def find_citation_contexts(
        self,
        comments: List[Dict],
        citation_type: str,
        section: Optional[str] = None,
        limit: int = 50,
    ) -> List[Dict]:
        """
        Find specific citation contexts for analysis.

        Args:
            comments: List of comment dicts
            citation_type: Type of citation (cfr, phsa, etc.)
            section: Specific section to find
            limit: Maximum results

        Returns:
            List of citation contexts
        """
        results = []

        for comment in comments:
            if len(results) >= limit:
                break

            text = comment.get("full_text", comment.get("comment_text", ""))
            comment_id = comment.get("id", "")

            citations = self.extract_all_citations(text)

            for citation in citations.get(citation_type, []):
                if section and citation.get("section") != section:
                    continue

                results.append({
                    "comment_id": comment_id,
                    "citation": citation.get("citation", citation.get("term", "")),
                    "context": citation["context"],
                    "stakeholder": comment.get("stakeholder", {}).get("category", ""),
                })

                if len(results) >= limit:
                    break

        return results


def main():
    """Main entry point for citation extractor."""
    import argparse

    parser = argparse.ArgumentParser(description="Extract regulatory citations from FDA comments")
    parser.add_argument("--input", help="Input JSON file")
    parser.add_argument("--output-dir", help="Output directory")
    parser.add_argument("--find", help="Find specific citation type (cfr, phsa, guidance, terms)")
    parser.add_argument("--section", help="Specific section to find")
    parser.add_argument("--limit", type=int, default=50, help="Max results for find")

    args = parser.parse_args()

    extractor = CitationExtractor()

    input_path = Path(args.input) if args.input else None
    comments = extractor.data_loader.load_comments_json(input_path)

    if not comments:
        logger.error("No comments found")
        return

    if args.find:
        results = extractor.find_citation_contexts(
            comments, args.find, args.section, args.limit
        )
        for r in results:
            print(f"\n[{r['comment_id']}] ({r['stakeholder']})")
            print(f"  {r['citation']}")
            print(f"  Context: {r['context']}")
    else:
        output_dir = Path(args.output_dir) if args.output_dir else None
        output_files = extractor.analyze_corpus(comments, output_dir)
        print(f"\nGenerated {len(output_files)} files:")
        for name, path in output_files.items():
            print(f"  - {name}: {path}")


if __name__ == "__main__":
    main()
