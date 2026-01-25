"""
Shared classification logic for FDA public comments.
Classifies comments into: Personal Narrative, Technical Document, Organizational.
"""
import re
import json
from pathlib import Path
from typing import Dict, List, Tuple, Optional
from collections import Counter

from . import config


class CommentClassifier:
    """Classify FDA public comments by type."""

    def __init__(self, technical_terms_path: Optional[Path] = None):
        """Initialize classifier with technical terms dictionary."""
        if technical_terms_path is None:
            technical_terms_path = config.DICTIONARIES_DIR / "technical_terms.json"

        self.technical_terms = self._load_technical_terms(technical_terms_path)
        self.personal_indicators = [p.lower() for p in config.PERSONAL_NARRATIVE_INDICATORS]
        self.technical_indicators = [t.lower() for t in config.TECHNICAL_DOCUMENT_INDICATORS]
        self.org_indicators = [o.lower() for o in config.ORGANIZATIONAL_INDICATORS]

    def _load_technical_terms(self, path: Path) -> List[str]:
        """Load technical terms from dictionary file."""
        terms = []
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)

            # Flatten all term lists
            for category in ["regulatory_citations", "technical_terms"]:
                if category in data:
                    for subcategory, term_list in data[category].items():
                        if isinstance(term_list, list):
                            terms.extend([t.lower() for t in term_list])

            if "legal_procedural_terms" in data:
                terms.extend([t.lower() for t in data["legal_procedural_terms"]])
            if "compliance_terms" in data:
                terms.extend([t.lower() for t in data["compliance_terms"]])

        except (FileNotFoundError, json.JSONDecodeError):
            # Use default minimal list if file not found
            terms = ["cfr", "phsa", "361", "351", "hctp", "regulation"]

        return terms

    def classify_comment_type(
        self, text: str, word_count: Optional[int] = None
    ) -> Dict[str, any]:
        """
        Classify a comment as Personal Narrative, Technical Document, or Organizational.

        Returns dict with:
            - type: str (personal_narrative, technical_document, organizational)
            - confidence: float (0-1)
            - signals: dict with detected indicators
        """
        if not text:
            return {
                "type": "unknown",
                "confidence": 0.0,
                "signals": {},
            }

        text_lower = text.lower()
        if word_count is None:
            word_count = len(text.split())

        # Calculate scores for each type
        personal_score = self._calculate_personal_score(text_lower, word_count)
        technical_score = self._calculate_technical_score(text_lower, word_count)
        org_score = self._calculate_organizational_score(text_lower)

        # Collect signals
        signals = {
            "personal_indicators": self._find_matches(text_lower, self.personal_indicators),
            "technical_indicators": self._find_matches(text_lower, self.technical_indicators),
            "organizational_indicators": self._find_matches(text_lower, self.org_indicators),
            "technical_density": self.calculate_technical_density(text_lower, word_count),
            "possessive_count": self.count_possessive_language(text_lower),
            "word_count": word_count,
        }

        # Determine classification
        scores = {
            "personal_narrative": personal_score,
            "technical_document": technical_score,
            "organizational": org_score,
        }

        max_type = max(scores, key=scores.get)
        max_score = scores[max_type]

        # Calculate confidence based on margin over other types
        other_scores = [s for t, s in scores.items() if t != max_type]
        margin = max_score - max(other_scores) if other_scores else max_score
        confidence = min(1.0, margin / 5.0 + 0.5) if max_score > 0 else 0.0

        return {
            "type": max_type,
            "confidence": round(confidence, 2),
            "signals": signals,
            "scores": scores,
        }

    def _calculate_personal_score(self, text: str, word_count: int) -> float:
        """Calculate personal narrative score."""
        score = 0.0

        # Count personal indicators
        matches = self._find_matches(text, self.personal_indicators)
        score += len(matches) * 1.5

        # High possessive language usage
        possessive_count = self.count_possessive_language(text)
        if possessive_count > 5:
            score += 2.0
        elif possessive_count > 2:
            score += 1.0

        # Moderate length (too long suggests technical/organizational)
        if word_count < config.MAX_WORDS_PERSONAL:
            score += 0.5

        # Low technical density
        density = self.calculate_technical_density(text, word_count)
        if density < config.TECHNICAL_DENSITY_THRESHOLD:
            score += 1.0

        return score

    def _calculate_technical_score(self, text: str, word_count: int) -> float:
        """Calculate technical document score."""
        score = 0.0

        # Count technical indicators
        matches = self._find_matches(text, self.technical_indicators)
        score += len(matches) * 1.0

        # High technical density
        density = self.calculate_technical_density(text, word_count)
        if density >= config.TECHNICAL_DENSITY_THRESHOLD:
            score += 2.0
        elif density >= 1.0:
            score += 1.0

        # Longer documents tend to be technical
        if word_count >= config.MIN_WORDS_TECHNICAL:
            score += 1.5
        elif word_count >= 250:
            score += 0.5

        # Low possessive language
        possessive_count = self.count_possessive_language(text)
        if possessive_count < 3:
            score += 0.5

        return score

    def _calculate_organizational_score(self, text: str) -> float:
        """Calculate organizational submission score."""
        score = 0.0

        # Count organizational indicators
        matches = self._find_matches(text, self.org_indicators)
        score += len(matches) * 2.0

        # Check for formal submission language
        formal_patterns = [
            r"respectfully\s+submit",
            r"on\s+behalf\s+of",
            r"our\s+(organization|association|company|members)",
            r"the\s+undersigned",
        ]
        for pattern in formal_patterns:
            if re.search(pattern, text):
                score += 1.5

        return score

    def _find_matches(self, text: str, patterns: List[str]) -> List[str]:
        """Find which patterns match in the text."""
        return [p for p in patterns if p in text]

    def calculate_technical_density(self, text: str, word_count: Optional[int] = None) -> float:
        """
        Calculate technical term density (terms per 100 words).
        """
        if not text:
            return 0.0

        text_lower = text.lower() if text != text.lower() else text
        if word_count is None:
            word_count = len(text.split())

        if word_count == 0:
            return 0.0

        # Count technical term occurrences
        term_count = 0
        for term in self.technical_terms:
            # Use word boundary matching for single words
            if " " in term:
                term_count += text_lower.count(term)
            else:
                pattern = r"\b" + re.escape(term) + r"\b"
                term_count += len(re.findall(pattern, text_lower))

        return round((term_count / word_count) * 100, 2)

    def count_possessive_language(self, text: str) -> int:
        """
        Count first-person possessive constructions.
        Returns total count of my/mine/our/ours usage.
        """
        if not text:
            return 0

        text_lower = text.lower() if text != text.lower() else text

        possessives = [r"\bmy\b", r"\bmine\b", r"\bour\b", r"\bours\b", r"\bmyself\b", r"\bourselves\b"]
        count = 0
        for pattern in possessives:
            count += len(re.findall(pattern, text_lower))

        return count

    def extract_possessive_contexts(self, text: str, window: int = 10) -> List[Dict]:
        """
        Extract possessive constructions with surrounding context.

        Args:
            text: Input text
            window: Number of words before/after to include

        Returns:
            List of dicts with possessive, context, and category
        """
        if not text:
            return []

        contexts = []
        words = text.split()

        possessive_patterns = {
            "my": "first_person_singular",
            "mine": "first_person_singular",
            "myself": "first_person_singular",
            "our": "first_person_plural",
            "ours": "first_person_plural",
            "ourselves": "first_person_plural",
        }

        for i, word in enumerate(words):
            word_clean = re.sub(r"[^\w]", "", word.lower())
            if word_clean in possessive_patterns:
                start = max(0, i - window)
                end = min(len(words), i + window + 1)
                context = " ".join(words[start:end])

                # Categorize what the possessive refers to
                following_words = " ".join(words[i : min(len(words), i + 4)]).lower()
                category = self._categorize_possessive_object(following_words)

                contexts.append({
                    "possessive": word_clean,
                    "type": possessive_patterns[word_clean],
                    "context": context,
                    "category": category,
                    "position": i,
                })

        return contexts

    def _categorize_possessive_object(self, following_text: str) -> str:
        """Categorize what a possessive pronoun refers to."""
        categories = {
            "body": ["body", "cells", "tissue", "blood", "bone", "fat", "marrow", "stem cells"],
            "health": ["health", "life", "condition", "disease", "pain", "symptoms", "diagnosis"],
            "treatment": ["treatment", "therapy", "procedure", "doctor", "physician", "care"],
            "family": ["husband", "wife", "son", "daughter", "mother", "father", "child", "family"],
            "organization": ["organization", "company", "clinic", "practice", "members", "patients"],
            "research": ["research", "study", "findings", "data", "laboratory"],
        }

        for category, keywords in categories.items():
            for keyword in keywords:
                if keyword in following_text:
                    return category

        return "other"


def classify_comment_type(text: str, word_count: Optional[int] = None) -> Dict:
    """Convenience function for quick classification."""
    classifier = CommentClassifier()
    return classifier.classify_comment_type(text, word_count)


def calculate_technical_density(text: str, word_count: Optional[int] = None) -> float:
    """Convenience function for technical density calculation."""
    classifier = CommentClassifier()
    return classifier.calculate_technical_density(text, word_count)


def count_possessive_language(text: str) -> int:
    """Convenience function for possessive language counting."""
    classifier = CommentClassifier()
    return classifier.count_possessive_language(text)
