"""
Tool 2: Docket Search Tool

Search regulations.gov API for related FDA dockets (HCTP, stem cell, etc.).
Useful for comparative analysis and context gathering.
"""
import logging
from pathlib import Path
from typing import Dict, List, Optional
from datetime import datetime
import time

import requests

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from utils import config
from utils.data_loader import DataLoader

logging.basicConfig(level=logging.INFO, format=config.LOG_FORMAT)
logger = logging.getLogger(__name__)


class DocketSearcher:
    """Search for related FDA dockets on regulations.gov."""

    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize the searcher.

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

    def search_dockets(
        self,
        search_term: str,
        agency: str = "FDA",
        start_date: Optional[str] = "2014-01-01",
        end_date: Optional[str] = None,
        max_results: int = 100,
    ) -> List[Dict]:
        """
        Search for dockets matching criteria.

        Args:
            search_term: Keyword to search for
            agency: Agency filter (default FDA)
            start_date: Start date filter (YYYY-MM-DD)
            end_date: End date filter
            max_results: Maximum results to return

        Returns:
            List of docket metadata dicts
        """
        dockets = []
        page = 1
        page_size = min(25, max_results)  # API limit

        while len(dockets) < max_results:
            params = {
                "filter[searchTerm]": search_term,
                "filter[agencyId]": agency,
                "page[size]": page_size,
                "page[number]": page,
            }

            if start_date:
                params["filter[postedDate][ge]"] = start_date
            if end_date:
                params["filter[postedDate][le]"] = end_date

            result = self._make_request("/dockets", params)
            if not result:
                break

            data = result.get("data", [])
            if not data:
                break

            for item in data:
                docket_info = self._extract_docket_info(item)
                dockets.append(docket_info)

            meta = result.get("meta", {})
            total_pages = meta.get("totalPages", 1)

            if page >= total_pages:
                break
            page += 1

        logger.info(f"Found {len(dockets)} dockets for '{search_term}'")
        return dockets[:max_results]

    def _extract_docket_info(self, item: Dict) -> Dict:
        """Extract relevant docket information."""
        attrs = item.get("attributes", {})
        return {
            "id": item.get("id", ""),
            "title": attrs.get("title", ""),
            "docket_type": attrs.get("docketType", ""),
            "agency": attrs.get("agencyId", ""),
            "modify_date": attrs.get("modifyDate", ""),
            "highlight": attrs.get("highlightedContent", ""),
            "object_id": attrs.get("objectId", ""),
        }

    def search_related_dockets(
        self,
        search_terms: Optional[List[str]] = None,
        start_date: str = "2014-01-01",
    ) -> Dict[str, List[Dict]]:
        """
        Search for dockets related to HCTP regulations.

        Args:
            search_terms: List of search terms (defaults to config)
            start_date: Start date for search

        Returns:
            Dict mapping search terms to found dockets
        """
        if search_terms is None:
            search_terms = config.RELATED_SEARCH_TERMS

        results = {}
        for term in search_terms:
            logger.info(f"Searching for: {term}")
            dockets = self.search_dockets(
                search_term=term,
                start_date=start_date,
            )
            results[term] = dockets

        return results

    def get_docket_details(self, docket_id: str) -> Optional[Dict]:
        """
        Get full details for a specific docket.

        Args:
            docket_id: Docket ID

        Returns:
            Full docket data
        """
        result = self._make_request(f"/dockets/{docket_id}")
        if not result:
            return None

        data = result.get("data", {})
        attrs = data.get("attributes", {})

        return {
            "id": data.get("id", ""),
            "title": attrs.get("title", ""),
            "docket_type": attrs.get("docketType", ""),
            "agency": attrs.get("agencyId", ""),
            "category": attrs.get("category", ""),
            "keywords": attrs.get("keywords", ""),
            "effective_date": attrs.get("effectiveDate", ""),
            "modify_date": attrs.get("modifyDate", ""),
            "rin": attrs.get("rin", ""),
            "program": attrs.get("program", ""),
        }

    def get_comment_count(self, docket_id: str) -> int:
        """
        Get total comment count for a docket.

        Args:
            docket_id: Docket ID

        Returns:
            Number of comments
        """
        params = {
            "filter[docketId]": docket_id,
            "page[size]": 1,
        }

        result = self._make_request("/comments", params)
        if not result:
            return 0

        meta = result.get("meta", {})
        return meta.get("totalElements", 0)

    def find_comparison_dockets(
        self,
        min_comments: int = 100,
        max_dockets: int = 20,
    ) -> List[Dict]:
        """
        Find FDA dockets suitable for comparison analysis.

        Args:
            min_comments: Minimum comment count
            max_dockets: Maximum dockets to return

        Returns:
            List of dockets with comment counts
        """
        # Search for various HCTP-related terms
        all_dockets = {}

        for term in config.RELATED_SEARCH_TERMS:
            dockets = self.search_dockets(term, max_results=50)
            for docket in dockets:
                if docket["id"] not in all_dockets:
                    all_dockets[docket["id"]] = docket

        # Get comment counts
        comparison_dockets = []
        for docket_id, docket in all_dockets.items():
            if docket_id == config.DOCKET_ID:
                continue  # Skip target docket

            count = self.get_comment_count(docket_id)
            if count >= min_comments:
                docket["comment_count"] = count
                comparison_dockets.append(docket)

            if len(comparison_dockets) >= max_dockets:
                break

        # Sort by comment count
        comparison_dockets.sort(key=lambda x: x.get("comment_count", 0), reverse=True)

        return comparison_dockets

    def export_search_results(
        self,
        results: Dict[str, List[Dict]],
        output_path: Optional[Path] = None,
    ) -> Path:
        """
        Export search results to JSON.

        Args:
            results: Search results dict
            output_path: Output file path

        Returns:
            Output path
        """
        if output_path is None:
            output_path = config.PROCESSED_DIR / "related_dockets.json"

        # Add metadata
        output = {
            "metadata": {
                "search_date": datetime.now().isoformat(),
                "target_docket": config.DOCKET_ID,
            },
            "results": results,
        }

        self.data_loader.save_json(output, output_path)
        logger.info(f"Saved search results to {output_path}")
        return output_path


def main():
    """Main entry point for docket search."""
    import argparse

    parser = argparse.ArgumentParser(description="Search for related FDA dockets")
    parser.add_argument("--term", help="Single search term")
    parser.add_argument("--all-related", action="store_true", help="Search all related terms")
    parser.add_argument("--comparison", action="store_true", help="Find comparison dockets")
    parser.add_argument("--docket", help="Get details for specific docket")

    args = parser.parse_args()

    searcher = DocketSearcher()

    if args.docket:
        details = searcher.get_docket_details(args.docket)
        count = searcher.get_comment_count(args.docket)
        print(f"Docket: {details}")
        print(f"Comment count: {count}")

    elif args.comparison:
        dockets = searcher.find_comparison_dockets()
        for d in dockets:
            print(f"{d['id']}: {d.get('comment_count', 0)} comments - {d['title'][:60]}")

    elif args.all_related:
        results = searcher.search_related_dockets()
        searcher.export_search_results(results)

    elif args.term:
        dockets = searcher.search_dockets(args.term)
        for d in dockets:
            print(f"{d['id']}: {d['title'][:80]}")

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
