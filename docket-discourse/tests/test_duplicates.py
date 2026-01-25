"""
Tests for MinHash/LSH duplicate detection.
"""
import pytest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    from datasketch import MinHash, MinHashLSH
    DATASKETCH_AVAILABLE = True
except ImportError:
    DATASKETCH_AVAILABLE = False

from analyzers.temporal_mapper import TemporalMapper


@pytest.fixture
def mapper():
    """Create a temporal mapper instance."""
    return TemporalMapper()


@pytest.fixture
def form_letter_comments():
    """Create test data with known duplicates."""
    base_text = """
    I am writing to express my opposition to the proposed FDA guidance on
    stem cell treatments. These treatments have helped thousands of patients
    and should remain available. Please reconsider this harmful regulation.
    """

    comments = []

    # Create 5 nearly identical form letters
    for i in range(5):
        comments.append({
            "id": f"form_letter_{i}",
            "comment_text": base_text,
            "full_text": base_text,
        })

    # Create 3 unique comments
    unique_texts = [
        "As a physician with 20 years of experience in regenerative medicine...",
        "The proposed guidance fails to account for the significant differences...",
        "Our research institution has conducted extensive clinical trials...",
    ]

    for i, text in enumerate(unique_texts):
        comments.append({
            "id": f"unique_{i}",
            "comment_text": text,
            "full_text": text,
        })

    return comments


@pytest.mark.skipif(not DATASKETCH_AVAILABLE, reason="datasketch not installed")
class TestDuplicateDetection:
    """Test MinHash/LSH duplicate detection."""

    def test_shingle_creation(self, mapper):
        """Test that shingles are created correctly."""
        text = "the quick brown fox jumps"

        shingles = mapper._create_shingles(text, k=3)

        assert len(shingles) == 3  # (the quick brown), (quick brown fox), (brown fox jumps)
        assert "the quick brown" in shingles
        assert "quick brown fox" in shingles

    def test_minhash_creation(self, mapper):
        """Test MinHash signature creation."""
        text = "This is a test document for minhash generation."

        mh = mapper._create_minhash(text)

        assert mh is not None
        assert len(mh.hashvalues) == mapper.num_perm

    def test_empty_text_minhash(self, mapper):
        """Test MinHash with empty text."""
        mh = mapper._create_minhash("")

        assert mh is None

    def test_similar_texts_high_similarity(self, mapper):
        """Test that similar texts have high Jaccard similarity."""
        text1 = "The FDA should reconsider the proposed guidance on stem cell treatments."
        text2 = "The FDA should reconsider the proposed guidance on stem cell therapy."

        mh1 = mapper._create_minhash(text1)
        mh2 = mapper._create_minhash(text2)

        similarity = mh1.jaccard(mh2)

        assert similarity > 0.7  # Should be quite similar

    def test_different_texts_low_similarity(self, mapper):
        """Test that different texts have low Jaccard similarity."""
        text1 = "The FDA should reconsider the proposed guidance."
        text2 = "Pursuant to CFR regulations, we submit technical comments."

        mh1 = mapper._create_minhash(text1)
        mh2 = mapper._create_minhash(text2)

        similarity = mh1.jaccard(mh2)

        assert similarity < 0.5  # Should be quite different

    def test_detect_duplicates(self, mapper, form_letter_comments):
        """Test duplicate detection on known data."""
        results = mapper.detect_duplicates(form_letter_comments)

        assert results["total_comments"] == 8
        assert results["duplicate_groups"] >= 1  # At least one group of form letters
        assert results["comments_in_groups"] >= 5  # The 5 form letters

    def test_unique_identification(self, mapper, form_letter_comments):
        """Test that unique comments are identified."""
        results = mapper.detect_duplicates(form_letter_comments)

        # Should identify ~3 unique comments
        assert results["unique_comments"] >= 3

    def test_duplicate_rate_calculation(self, mapper, form_letter_comments):
        """Test duplicate rate calculation."""
        results = mapper.detect_duplicates(form_letter_comments)

        # 5 out of 8 comments are duplicates = 62.5%
        assert 50 < results["duplicate_rate"] < 80

    def test_group_extraction(self, mapper, form_letter_comments):
        """Test that duplicate groups are properly extracted."""
        results = mapper.detect_duplicates(form_letter_comments)
        groups = results.get("groups", [])

        if groups:
            # Check that groups have required fields
            for group in groups:
                assert "group_id" in group
                assert "size" in group
                assert "comment_ids" in group
                assert group["size"] >= 2  # Groups must have at least 2

    def test_sample_extraction(self, mapper, form_letter_comments):
        """Test extraction of sample comments from groups."""
        results = mapper.detect_duplicates(form_letter_comments)
        samples = mapper.extract_group_samples(form_letter_comments, results)

        if results["duplicate_groups"] > 0:
            assert len(samples) >= 1
            assert "group_id" in samples[0]
            assert "text_preview" in samples[0]

    def test_threshold_sensitivity(self, mapper, form_letter_comments):
        """Test that different thresholds produce different results."""
        results_high = mapper.detect_duplicates(form_letter_comments, threshold=0.95)
        results_low = mapper.detect_duplicates(form_letter_comments, threshold=0.5)

        # Lower threshold should find more duplicates
        assert results_low["comments_in_groups"] >= results_high["comments_in_groups"]


class TestTimelineBuilding:
    """Test timeline construction."""

    def test_parse_date_iso(self, mapper):
        """Test ISO date parsing."""
        date_str = "2016-01-15T12:00:00Z"
        parsed = mapper.parse_date(date_str)

        assert parsed is not None
        assert parsed.year == 2016
        assert parsed.month == 1
        assert parsed.day == 15

    def test_parse_date_simple(self, mapper):
        """Test simple date parsing."""
        date_str = "2016-01-15"
        parsed = mapper.parse_date(date_str)

        assert parsed is not None
        assert parsed.year == 2016

    def test_parse_invalid_date(self, mapper):
        """Test handling of invalid dates."""
        parsed = mapper.parse_date("not a date")

        assert parsed is None

    def test_timeline_building(self, mapper):
        """Test timeline DataFrame construction."""
        comments = [
            {"id": "1", "posted_date": "2016-01-15"},
            {"id": "2", "posted_date": "2016-01-15"},
            {"id": "3", "posted_date": "2016-01-16"},
        ]

        timeline = mapper.build_timeline(comments)

        assert not timeline.empty
        assert "date" in timeline.columns
        assert "count" in timeline.columns
        assert "cumulative" in timeline.columns
        assert timeline["cumulative"].iloc[-1] == 3
