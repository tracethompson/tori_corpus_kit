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
        "classification": {
            "type": "personal_narrative",
            "confidence": 0.8,
            "signals": {
                "possessive_count": 1,
                "technical_density": 0.0,
            },
        },
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
            "classification": {"type": "personal_narrative"},
        }
        for i in range(10)
    ]


@pytest.fixture
def personal_narrative_text():
    """Sample personal narrative text."""
    return """
    I am writing to share my personal experience with stem cell therapy.
    My condition was diagnosed three years ago, and my doctors told me
    there was nothing conventional medicine could do. After my treatment,
    my pain decreased significantly. My quality of life has improved.
    I believe my cells, my body, should be my choice.
    """


@pytest.fixture
def technical_document_text():
    """Sample technical document text."""
    return """
    Pursuant to 21 CFR Part 1271.10, we submit these comments regarding
    the draft guidance. Section 361 of the PHSA establishes the regulatory
    framework for HCT/Ps. The minimal manipulation criteria should be
    interpreted consistently with the statutory authority granted under
    Section 351. We respectfully request clarification on homologous use.
    """


@pytest.fixture
def organizational_text():
    """Sample organizational submission text."""
    return """
    On behalf of the American Association of Regenerative Medicine, we
    respectfully submit these comments. Our organization represents over
    500 member clinics. Our members collectively serve thousands of patients.
    The undersigned organizations urge the FDA to reconsider the proposed
    guidance. We submit that the proposed framework is overly restrictive.
    """
