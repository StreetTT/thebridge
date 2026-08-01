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

    # Savings interest accrual. The property *names* are env-tunable so the
    # Accounts schema can be renamed without touching code; their *values* live
    # in Notion (the single source of truth for accrual state).
    SAVINGS_EARNS_INTEREST_PROPERTY = os.environ.get(
        "SAVINGS_EARNS_INTEREST_PROPERTY", "Earns Interest"
    )
    SAVINGS_AER_PROPERTY = os.environ.get("SAVINGS_AER_PROPERTY", "AER")
    SAVINGS_PAYMENT_DAY_PROPERTY = os.environ.get(
        "SAVINGS_PAYMENT_DAY_PROPERTY", "Interest Payment Day"
    )
    SAVINGS_BALANCE_PROPERTY = os.environ.get(
        "SAVINGS_BALANCE_PROPERTY", "Current Balance"
    )
    SAVINGS_ACCRUED_PROPERTY = os.environ.get(
        "SAVINGS_ACCRUED_PROPERTY", "Accrued Interest"
    )
    SAVINGS_LAST_ACCRUED_PROPERTY = os.environ.get(
        "SAVINGS_LAST_ACCRUED_PROPERTY", "Last Accrued"
    )
    SAVINGS_LAST_PAID_PROPERTY = os.environ.get(
        "SAVINGS_LAST_PAID_PROPERTY", "Last Interest Paid"
    )

    # Title + category applied to the monthly interest transaction.
    SAVINGS_INTEREST_NAME = os.environ.get("SAVINGS_INTEREST_NAME", "Interest")
    SAVINGS_INTEREST_CATEGORY = os.environ.get("SAVINGS_INTEREST_CATEGORY", "Interest")
