"""
Tests for comment type classification.
"""
import pytest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from utils.comment_classifier import CommentClassifier, classify_comment_type


@pytest.fixture
def classifier():
    """Create a classifier instance."""
    return CommentClassifier()


class TestCommentClassifier:
    """Test comment type classification."""

    def test_personal_narrative_detection(self, classifier):
        """Test that personal narratives are correctly identified."""
        text = """
        My name is Jane and I am a patient who has benefited greatly from stem cell
        therapy. My condition was degenerative and my doctors said there was nothing
        they could do. After my treatment, my pain decreased significantly and my
        quality of life improved. I believe this therapy saved my life.
        """

        result = classifier.classify_comment_type(text)

        assert result["type"] == "personal_narrative"
        assert result["confidence"] > 0.5
        assert result["signals"]["possessive_count"] > 5

    def test_technical_document_detection(self, classifier):
        """Test that technical documents are correctly identified."""
        text = """
        Pursuant to 21 CFR Part 1271, we submit this comment regarding the draft
        guidance on same surgical procedure exception. Section 361 of the PHSA
        establishes the regulatory framework for HCT/Ps. The minimal manipulation
        criteria set forth in 21 CFR 1271.10 should be interpreted to allow
        autologous procedures that maintain homologous use. We believe the proposed
        guidance exceeds FDA's statutory authority under Section 351 of the PHSA.
        """

        result = classifier.classify_comment_type(text)

        assert result["type"] == "technical_document"
        assert result["signals"]["technical_density"] > 1.0

    def test_organizational_detection(self, classifier):
        """Test that organizational submissions are correctly identified."""
        text = """
        On behalf of the American Association of Regenerative Medicine Clinics,
        we respectfully submit the following comments. Our organization represents
        over 500 member clinics nationwide. Our members have collectively treated
        thousands of patients. We urge the FDA to reconsider the proposed guidance.
        The undersigned organizations support patient access to innovative therapies.
        """

        result = classifier.classify_comment_type(text)

        assert result["type"] == "organizational"
        assert len(result["signals"]["organizational_indicators"]) > 0

    def test_empty_text(self, classifier):
        """Test handling of empty text."""
        result = classifier.classify_comment_type("")

        assert result["type"] == "unknown"
        assert result["confidence"] == 0.0

    def test_short_ambiguous_text(self, classifier):
        """Test handling of short, ambiguous text."""
        text = "I support this guidance."

        result = classifier.classify_comment_type(text)

        assert "type" in result
        assert result["confidence"] < 0.8  # Should have low confidence

    def test_possessive_count(self, classifier):
        """Test possessive language counting."""
        text = "My cells are my own. Our bodies belong to ourselves."

        count = classifier.count_possessive_language(text)

        assert count == 4  # my, my, our, ourselves

    def test_technical_density(self, classifier):
        """Test technical term density calculation."""
        # 100 words with ~5 technical terms
        text = " ".join(["word"] * 95) + " CFR PHSA HCT/P regulation guidance"

        density = classifier.calculate_technical_density(text)

        assert density > 0
        assert density < 10

    def test_possessive_context_extraction(self, classifier):
        """Test extraction of possessive contexts."""
        text = "I went to the clinic because my condition was getting worse. My doctor recommended treatment."

        contexts = classifier.extract_possessive_contexts(text)

        assert len(contexts) == 2
        assert contexts[0]["possessive"] == "my"
        assert "condition" in contexts[0]["context"].lower()

    def test_possessive_categorization(self, classifier):
        """Test that possessive objects are categorized correctly."""
        text = "My cells were extracted from my body for my treatment."

        contexts = classifier.extract_possessive_contexts(text)

        categories = [c["category"] for c in contexts]
        assert "body" in categories or "health" in categories or "treatment" in categories


class TestConvenienceFunctions:
    """Test module-level convenience functions."""

    def test_classify_comment_type(self):
        """Test convenience classification function."""
        text = "I am a patient who benefited from my treatment."
        result = classify_comment_type(text)

        assert "type" in result
        assert "confidence" in result


class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_unicode_text(self, classifier):
        """Test handling of unicode characters."""
        text = "My térmînos and côndîtîons are améliórátéd."

        result = classifier.classify_comment_type(text)

        assert "type" in result

    def test_very_long_text(self, classifier):
        """Test handling of very long text."""
        text = " ".join(["My condition improved after treatment."] * 1000)

        result = classifier.classify_comment_type(text)

        assert "type" in result
        assert result["signals"]["word_count"] > 5000

    def test_mixed_signals(self, classifier):
        """Test text with mixed classification signals."""
        text = """
        On behalf of our organization, I want to share my personal story.
        My treatment helped me, but pursuant to 21 CFR 1271, we believe
        the guidance should be modified. Our members support this position.
        """

        result = classifier.classify_comment_type(text)

        # Should classify but may have lower confidence due to mixed signals
        assert "type" in result
        assert len(result["signals"]["personal_indicators"]) > 0
        assert len(result["signals"]["organizational_indicators"]) > 0
