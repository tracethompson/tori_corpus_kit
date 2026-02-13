"""
Central configuration for docket-discourse analysis suite.
"""
import os
from pathlib import Path
from datetime import datetime

# Load .env file if present
try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).parent.parent / ".env")
except ImportError:
    pass  # dotenv not installed, rely on environment variables

# =============================================================================
# API Configuration
# =============================================================================
REGULATIONS_GOV_API_KEY = os.environ.get("REGULATIONS_GOV_API_KEY", "")
REGULATIONS_API_BASE = "https://api.regulations.gov/v4"

# Rate limiting (1000 requests/hour for default key)
RATE_LIMIT_DELAY = 3.6  # seconds between requests (safe margin)
REQUESTS_PER_HOUR = 1000
CHECKPOINT_INTERVAL = 100  # Save progress every N comments

# =============================================================================
# Target Docket Configuration
# =============================================================================
DOCKET_ID = "FDA-2015-D-3719"
EXPECTED_COMMENT_COUNT = 6950

# Date ranges for analysis
DOCKET_OPEN_DATE = datetime(2015, 12, 22)
DOCKET_CLOSE_DATE = datetime(2016, 3, 28)

# Related search terms for finding similar dockets
RELATED_SEARCH_TERMS = [
    "HCTP",
    "human cells tissues cellular",
    "stem cell",
    "regenerative medicine",
    "351 PHSA",
    "361 PHSA",
    "21 CFR 1271",
]

# =============================================================================
# File Paths
# =============================================================================
PROJECT_ROOT = Path(__file__).parent.parent
DATA_DIR = PROJECT_ROOT / "data"
RAW_DIR = DATA_DIR / "raw"
PROCESSED_DIR = DATA_DIR / "processed"
OUTPUTS_DIR = DATA_DIR / "outputs"
DICTIONARIES_DIR = PROJECT_ROOT / "dictionaries"

# Output subdirectories
TABLES_DIR = OUTPUTS_DIR / "tables"
FIGURES_DIR = OUTPUTS_DIR / "figures"
QUOTES_DIR = OUTPUTS_DIR / "quotes"

# =============================================================================
# MinHash/LSH Configuration (Duplicate Detection)
# =============================================================================
MINHASH_NUM_PERM = 128  # Number of permutations
SIMILARITY_THRESHOLD = 0.9  # Threshold for near-duplicates
SHINGLE_SIZE = 3  # Word n-gram size for shingling

# =============================================================================
# Frame Analysis Configuration
# =============================================================================
FRAME_CATEGORIES = {
    "body_self": {
        "name": "Body/Self",
        "indicators": [
            "my body", "my cells", "my tissue", "my blood",
            "my own", "myself", "my health", "my life",
            "bodily autonomy", "personal choice", "self-determination",
        ],
    },
    "product_drug": {
        "name": "Product/Drug",
        "indicators": [
            "drug product", "biological product", "medical product",
            "manufactured", "processed", "manipulated",
            "fda approval", "regulated product", "safety testing",
        ],
    },
    "treatment_therapy": {
        "name": "Treatment/Therapy",
        "indicators": [
            "treatment", "therapy", "procedure", "medical practice",
            "physician", "doctor", "patient care", "clinical",
            "healing", "recovery", "cure", "relief",
        ],
    },
    "economic_access": {
        "name": "Economic/Access",
        "indicators": [
            "cost", "expensive", "affordable", "access",
            "insurance", "coverage", "out of pocket", "price",
            "availability", "barrier", "restriction",
        ],
    },
}

# =============================================================================
# Export Configuration
# =============================================================================
FIGURE_DPI = 300
FIGURE_FORMAT_RASTER = "png"
FIGURE_FORMAT_VECTOR = "pdf"

# MLA 8 citation format
CITATION_AUTHOR = "U.S. Food and Drug Administration"
CITATION_TITLE = "Public Comments on Draft Guidance: Same Surgical Procedure Exception"
CITATION_DOCKET = "FDA-2015-D-3719"

# =============================================================================
# Logging Configuration
# =============================================================================
LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
LOG_LEVEL = "INFO"


def ensure_directories():
    """Create all required directories if they don't exist."""
    for directory in [RAW_DIR, PROCESSED_DIR, TABLES_DIR, FIGURES_DIR, QUOTES_DIR]:
        directory.mkdir(parents=True, exist_ok=True)


def validate_api_key():
    """Check if API key is configured."""
    if not REGULATIONS_GOV_API_KEY:
        raise ValueError(
            "REGULATIONS_GOV_API_KEY environment variable not set. "
            "Get your API key from https://api.regulations.gov"
        )
    return True
