"""
Tests for stakeholder classification.
"""
import pytest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from analyzers.stakeholder_classifier import StakeholderClassifier


@pytest.fixture
def classifier():
    """Create a stakeholder classifier instance."""
    return StakeholderClassifier()


class TestStakeholderClassification:
    """Test stakeholder type classification."""

    def test_patient_classification(self, classifier):
        """Test patient stakeholder detection."""
        text = """
        As a patient who has received stem cell treatment, I want to share my story.
        I was diagnosed with a degenerative condition. My treatment helped my pain
        and improved my quality of life. I am grateful for my doctor's care.
        """

        result = classifier.classify_stakeholder(text)

        assert result["category"] == "patient"
        assert result["score"] > 0

    def test_healthcare_provider_classification(self, classifier):
        """Test healthcare provider detection."""
        text = """
        As a physician with over 20 years of experience in regenerative medicine,
        I have treated hundreds of patients with these procedures. In my practice,
        I have seen significant patient outcomes. As a doctor, I believe the
        proposed guidance will harm my patients.
        """

        result = classifier.classify_stakeholder(text, "John Smith, MD")

        assert result["category"] == "healthcare_provider"
        assert "MD" in result["credentials_found"]

    def test_industry_classification(self, classifier):
        """Test industry stakeholder detection."""
        text = """
        On behalf of our company, BioTech Solutions Inc., we submit these comments.
        Our organization manufactures regenerative medicine products. We process
        over 10,000 units annually. Our products meet the highest standards.
        """

        result = classifier.classify_stakeholder(text)

        assert result["category"] in ["industry", "clinic_operator"]

    def test_researcher_classification(self, classifier):
        """Test researcher detection."""
        text = """
        Our research team at the university has conducted extensive studies
        on stem cell therapies. Our published findings in peer-reviewed journals
        demonstrate the safety of these procedures. As principal investigator
        of our clinical trial, I can attest to the scientific basis.
        """

        result = classifier.classify_stakeholder(text, "Jane Doe, PhD")

        assert result["category"] == "researcher"
        assert "PhD" in result["credentials_found"]

    def test_patient_advocate_classification(self, classifier):
        """Test patient advocate detection."""
        text = """
        My husband was diagnosed with a terminal illness. As his caregiver,
        I watched him suffer. Our family sought every possible treatment.
        I write on behalf of patients and their loved ones who deserve access
        to these therapies.
        """

        result = classifier.classify_stakeholder(text)

        assert result["category"] in ["patient_advocate", "patient"]

    def test_legal_professional_classification(self, classifier):
        """Test legal professional detection."""
        text = """
        As an attorney specializing in FDA regulatory matters, I submit this
        legal analysis. In my legal opinion, the proposed guidance exceeds
        the agency's statutory authority. Our law firm represents clients
        in this space.
        """

        result = classifier.classify_stakeholder(text, "Robert Jones, Esq.")

        assert result["category"] == "legal_professional"

    def test_general_public_classification(self, classifier):
        """Test general public detection."""
        text = """
        As a concerned citizen, I believe the FDA should reconsider this guidance.
        I think patient access is important. In my opinion, regulations should
        not restrict medical innovation.
        """

        result = classifier.classify_stakeholder(text)

        # May classify as general_public or patient depending on signals
        assert result["category"] in ["general_public", "patient", "unknown"]


class TestCredentialExtraction:
    """Test professional credential extraction."""

    def test_extract_md_credential(self, classifier):
        """Test MD credential extraction."""
        text = "John Smith, M.D., is a board-certified physician."

        credentials = classifier.extract_credentials(text)

        assert any("M.D" in c or "MD" in c for c in credentials)

    def test_extract_phd_credential(self, classifier):
        """Test PhD credential extraction."""
        text = "Dr. Jane Doe, Ph.D., leads the research team."

        credentials = classifier.extract_credentials(text)

        assert any("Ph.D" in c or "PhD" in c for c in credentials)

    def test_extract_multiple_credentials(self, classifier):
        """Test extraction of multiple credentials."""
        text = "The panel includes John MD, Jane PhD, and Bob JD."

        credentials = classifier.extract_credentials(text)

        assert len(credentials) >= 2

    def test_no_credentials(self, classifier):
        """Test text with no credentials."""
        text = "This is a comment from an anonymous person."

        credentials = classifier.extract_credentials(text)

        assert len(credentials) == 0


class TestConfidenceScoring:
    """Test confidence level assignment."""

    def test_high_confidence_classification(self, classifier):
        """Test that strong signals produce high confidence."""
        text = """
        As a physician, I am a doctor treating patients in my practice.
        I have treated my patients with these therapies. My medical experience
        shows that patient outcomes are excellent. As a healthcare provider,
        I urge the FDA to reconsider.
        """

        result = classifier.classify_stakeholder(text, "Dr. Smith, MD")

        # Strong signals should produce high confidence
        assert result["confidence"] in ["high", "medium"]

    def test_low_confidence_for_weak_signals(self, classifier):
        """Test that weak signals produce low confidence."""
        text = "Thank you."

        result = classifier.classify_stakeholder(text)

        assert result["confidence"] == "low"

    def test_all_scores_included(self, classifier):
        """Test that all category scores are included."""
        text = "I am a patient who needs treatment for my condition."

        result = classifier.classify_stakeholder(text)

        assert "all_scores" in result
        assert len(result["all_scores"]) > 0


class TestExclusionRules:
    """Test exclusion rules that prevent misclassification."""

    def test_industry_language_reduces_patient_score(self, classifier):
        """Test that organizational language reduces patient classification."""
        text = """
        On behalf of our company, we submit these comments. While our CEO
        was once a patient, we now manufacture these products for our customers.
        """

        result = classifier.classify_stakeholder(text)

        # Should not classify as patient despite "patient" mention
        assert result["category"] != "patient"


class TestValidationSample:
    """Test validation sample generation."""

    def test_validation_sample_structure(self, classifier):
        """Test that validation samples have correct structure."""
        comments = [
            {
                "id": "1",
                "full_text": "I am a patient who benefited from treatment.",
                "submitter_name": "John Doe",
            },
        ]

        sample = classifier.validate_sample(comments, sample_size=1)

        assert len(sample) == 1
        assert "comment_id" in sample[0]
        assert "predicted_category" in sample[0]
        assert "manual_category" in sample[0]  # For human reviewer
