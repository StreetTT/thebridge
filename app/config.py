"""Application configuration.

Loads secrets and Notion data source IDs from the environment.
"""

import os
from pathlib import Path

try:
    from dotenv import load_dotenv

    # Load the .env sitting next to the project root, not the process CWD.
    # Under PythonAnywhere's WSGI server the CWD is not the project folder,
    # so a bare load_dotenv() would silently find nothing.
    _PROJECT_ROOT = Path(__file__).resolve().parent.parent
    load_dotenv(_PROJECT_ROOT / ".env")
except ImportError:  # python-dotenv is optional at runtime
    pass


class Config:
    """Base config read from environment variables."""

    # Secrets
    NOTION_TOKEN = os.environ.get("NOTION_TOKEN", "")
    API_SECRET = os.environ.get("API_SECRET", "")

    # Notion API
    NOTION_VERSION = os.environ.get("NOTION_VERSION", "2025-09-03")

    # Notion data source IDs
    TRANSACTIONS_DS_ID = os.environ.get("TRANSACTIONS_DS_ID", "")
    ACCOUNTS_DS_ID = os.environ.get("ACCOUNTS_DS_ID", "")
    CATEGORIES_DS_ID = os.environ.get("CATEGORIES_DS_ID", "")
    MONTHS_DS_ID = os.environ.get("MONTHS_DS_ID", "")
