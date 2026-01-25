"""
Tests for rhetorical frame detection.
"""
import pytest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from analyzers.frame_detector import FrameDetector


@pytest.fixture
def detector():
    """Create a frame detector instance."""
    return FrameDetector()


class TestFrameDetection:
    """Test frame detection logic."""

    def test_body_self_frame_detection(self, detector):
        """Test detection of Body/Self framing."""
        text = """
        My body belongs to me. My cells are my own property. I have the right
        to use my own tissues for my health. This is about bodily autonomy
        and self-determination. No one should tell me what I can do with myself.
        """

        results = detector.detect_frames(text)

        assert results["body_self"]["present"]
        assert results["body_self"]["score"] > 0
        assert len(results["body_self"]["matches"]) > 0

    def test_product_drug_frame_detection(self, detector):
        """Test detection of Product/Drug framing."""
        text = """
        These are biological products that require FDA approval. The drug product
        must undergo safety testing. Manufacturing processes need to be validated.
        This is a regulated product subject to premarket approval requirements.
        """

        results = detector.detect_frames(text)

        assert results["product_drug"]["present"]
        assert results["product_drug"]["score"] > 0

    def test_treatment_therapy_frame_detection(self, detector):
        """Test detection of Treatment/Therapy framing."""
        text = """
        My physician recommended this treatment for my condition. The therapy
        has helped many patients. This is a medical procedure performed by doctors.
        Patient care should be the priority. The clinical outcomes speak for themselves.
        """

        results = detector.detect_frames(text)

        assert results["treatment_therapy"]["present"]
        assert results["treatment_therapy"]["score"] > 0

    def test_economic_access_frame_detection(self, detector):
        """Test detection of Economic/Access framing."""
        text = """
        The cost of FDA-approved treatments is prohibitive. Patients cannot
        afford these expensive procedures. Insurance coverage is limited.
        Access to care should not depend on ability to pay. These regulations
        create barriers for patients seeking affordable treatment.
        """

        results = detector.detect_frames(text)

        assert results["economic_access"]["present"]
        assert results["economic_access"]["score"] > 0

    def test_multiple_frames_present(self, detector):
        """Test detection of multiple frames in same text."""
        text = """
        My body is my own and I should have access to affordable treatments.
        This therapy helped me when expensive drug products were out of reach.
        """

        results = detector.detect_frames(text)

        frames_present = sum(1 for f in results.values() if f["present"])
        assert frames_present >= 2

    def test_no_frames_present(self, detector):
        """Test text with no clear framing."""
        text = "Thank you for the opportunity to comment on this matter."

        results = detector.detect_frames(text)

        total_score = sum(f["score"] for f in results.values())
        assert total_score == 0 or all(f["score"] < 2 for f in results.values())

    def test_empty_text(self, detector):
        """Test handling of empty text."""
        results = detector.detect_frames("")

        assert all(not f["present"] for f in results.values())
        assert all(f["score"] == 0 for f in results.values())

    def test_frame_names_included(self, detector):
        """Test that human-readable frame names are included."""
        text = "My body, my choice."

        results = detector.detect_frames(text)

        assert results["body_self"]["frame_name"] == "Body/Self"
        assert results["product_drug"]["frame_name"] == "Product/Drug"


class TestPossessiveFrameAnalysis:
    """Test possessive construction analysis by frame."""

    def test_possessive_frames_body(self, detector):
        """Test possessive frame analysis for body-related language."""
        text = "My cells, my body, my choice. These are my tissues from my own body."

        poss_frames = detector.analyze_possessive_frames(text)

        # Should find body/self frame possessives
        assert len(poss_frames) > 0

    def test_possessive_frames_treatment(self, detector):
        """Test possessive frame analysis for treatment-related language."""
        text = "My treatment was successful. My doctor recommended my therapy."

        poss_frames = detector.analyze_possessive_frames(text)

        # Should categorize by frame
        assert isinstance(poss_frames, dict)


class TestDiscoveryMode:
    """Test discovery mode for finding new indicators."""

    def test_discovery_returns_structure(self, detector):
        """Test that discovery mode returns expected structure."""
        comments = [
            {"full_text": "My cells helped my condition.", "id": "1"},
            {"full_text": "The treatment was effective.", "id": "2"},
        ]

        discoveries = detector.run_discovery_mode(comments, sample_size=2)

        assert "frequent_noun_phrases" in discoveries or discoveries == {}
        # May be empty if spaCy not available

    def test_discovery_with_empty_comments(self, detector):
        """Test discovery mode with empty input."""
        discoveries = detector.run_discovery_mode([], sample_size=10)

        assert isinstance(discoveries, dict)


class TestTargetedSearch:
    """Test targeted frame search."""

    def test_targeted_search_finds_matches(self, detector):
        """Test that targeted search finds high-scoring comments."""
        comments = [
            {
                "id": "high_body",
                "full_text": "My body, my cells, my choice. My tissues are my own.",
            },
            {
                "id": "low_body",
                "full_text": "The regulation should be reconsidered.",
            },
        ]

        results = detector.targeted_search(comments, "body_self", min_score=2)

        assert len(results) >= 1
        assert results[0]["comment_id"] == "high_body"

    def test_targeted_search_respects_threshold(self, detector):
        """Test that min_score threshold is respected."""
        comments = [
            {"id": "1", "full_text": "My body is important."},
        ]

        results_high = detector.targeted_search(comments, "body_self", min_score=10)
        results_low = detector.targeted_search(comments, "body_self", min_score=1)

        assert len(results_low) >= len(results_high)
