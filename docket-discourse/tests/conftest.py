"""
pytest configuration and shared fixtures.
"""
import pytest
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))


@pytest.fixture
def sample_comment():
    """Create a sample comment dict."""
    return {
        "id": "test-comment-001",
        "document_id": "test-comment-001",
        "title": "Test Comment",
        "submitter_name": "John Doe",
        "posted_date": "2016-01-15T12:00:00Z",
        "comment_text": "This is a test comment about my treatment.",
        "full_text": "This is a test comment about my treatment.",
        "word_count": 9,
        "has_attachments": False,
        "attachments": [],
    }


@pytest.fixture
def sample_comments():
    """Create a list of sample comments."""
    return [
        {
            "id": f"test-{i}",
            "comment_text": f"Sample comment text {i}",
            "full_text": f"Sample comment text {i}",
            "word_count": 4,
            "posted_date": f"2016-01-{15+i:02d}",
        }
        for i in range(10)
    ]
