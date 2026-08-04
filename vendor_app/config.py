# Validates Config Information
import os
from pathlib import Path
from dotenv import load_dotenv

# Define some directories
BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "knowledge_base"
PROMPT_PATH = BASE_DIR / "templates" / "human_review_v1.json"

# Let's get our env variables and give them some handy defaults if needed
load_dotenv(BASE_DIR / ".env")

MODEL_NAME = os.getenv("GEMINI_MODEL", "gemini-3.1-flash-lite")
EMBEDDING_MODEL_NAME = os.getenv(
    "EMBEDDING_MODEL",
    "sentence-transformers/all-MiniLM-L6-v2"
)
COLLECTION_NAME = "vendor_documents"


def validate_settings() -> None:

    if not os.getenv("GOOGLE_API_KEY"):
        raise RuntimeError(
            "GOOGLE_API_KEY environment variable not set"
        )

    if not DATA_DIR.exists():
        raise RuntimeError(
            "Knowledge Base Directory does not exist"
        )

    if not PROMPT_PATH.exists():
        raise RuntimeError(
            "Prompt file does not exist"
        )