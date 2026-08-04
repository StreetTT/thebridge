"""Thin Notion API wrapper (requests-based).

Only the pieces the bridge needs: resolve a page id from its title
(:meth:`NotionClient.query_by_name`), read whole rows of a data source
(:meth:`NotionClient.query_all`), create a transaction page
(:meth:`NotionClient.create_page`), and patch an existing page
(:meth:`NotionClient.update_page`). All calls target the
2025-09-03 API, where pages are parented by ``data_source_id`` and lookup
tables are queried at ``/v1/data_sources/{id}/query``.
"""

import logging
import time

import requests

_API_ROOT = "https://api.notion.com/v1"
# PythonAnywhere's free tier is slow to reach out; give Notion room to answer.
_TIMEOUT = 15
_log = logging.getLogger(__name__)


class NotionError(Exception):
    """A failure talking to Notion, carrying the HTTP status the client sees.

    The message flows into the ``{status, message}`` response the Apple
    Shortcut treats as an error (it keys off the presence of ``status``).
    """

    def __init__(self, message: str, code: int = 502):
        super().__init__(message)
        self.code = code


class NotionClient:
    """Minimal Notion client scoped to the bridge's needs."""

    def __init__(self, token: str, version: str):
        if not token:
            raise NotionError("Server missing NOTION_TOKEN", code=500)
        self._headers = {
            "Authorization": f"Bearer {token}",
            "Notion-Version": version,
            "Content-Type": "application/json",
        }

    def query_by_name(self, data_source_id: str, name: str) -> str | None:
        """Return the id of the page whose title equals ``name``, else ``None``.

        Matching is case-insensitive and trims whitespace. Results are paged
        through so small lookup tables (categories, months, accounts) resolve
        reliably without needing to know each table's title property name.
        """
        if not name:
            return None
        target = name.strip().lower()
        cursor = None
        while True:
            payload: dict = {"page_size": 100}
            if cursor:
                payload["start_cursor"] = cursor
            data = self._post(f"/data_sources/{data_source_id}/query", payload)
            for page in data.get("results", []):
                if _page_title(page).strip().lower() == target:
                    return page.get("id")
            if not data.get("has_more"):
                return None
            cursor = data.get("next_cursor")

    def list_names(self, data_source_id: str) -> list[str]:
        """Return every non-empty page title in a data source, in Notion's order.

        Used to offer the full category list when a merchant's category is
        ambiguous or unknown. Pages through the whole (small) table.
        """
        names: list[str] = []
        cursor = None
        while True:
            payload: dict = {"page_size": 100}
            if cursor:
                payload["start_cursor"] = cursor
            data = self._post(f"/data_sources/{data_source_id}/query", payload)
            for page in data.get("results", []):
                title = _page_title(page).strip()
                if title:
                    names.append(title)
            if not data.get("has_more"):
                return names
            cursor = data.get("next_cursor")

    def query_all(self, data_source_id: str) -> list[dict]:
        """Return every page in a data source as its full Notion dict.

        Unlike :meth:`list_names`, callers get the raw page (including each
        property's ``checkbox``/``number``/``date``/``formula`` value), so they
        can read arbitrary columns. Pages through the whole table, mirroring the
        pagination in :meth:`list_names`.
        """
        pages: list[dict] = []
        cursor = None
        while True:
            payload: dict = {"page_size": 100}
            if cursor:
                payload["start_cursor"] = cursor
            data = self._post(f"/data_sources/{data_source_id}/query", payload)
            pages.extend(data.get("results", []))
            if not data.get("has_more"):
                return pages
            cursor = data.get("next_cursor")

    def list_accounts(
        self, data_source_id: str, alias_property: str, archived_property: str
    ) -> list[dict]:
        """Return each account row as ``{"id", "codename", "apple_card"}``.

        ``codename`` is the page title; ``apple_card`` is the plain-text value of
        ``alias_property`` (the exact name Apple hands over), empty when unset.
        Rows without a title, or rows whose ``archived_property`` checkbox is
        ticked, are skipped. Results are returned in reverse of Notion's query
        order (newest-defined accounts last become first). Pages through the
        whole (small) table, mirroring :meth:`list_names`.
        """
        accounts: list[dict] = []
        cursor = None
        while True:
            payload: dict = {"page_size": 100}
            if cursor:
                payload["start_cursor"] = cursor
            data = self._post(f"/data_sources/{data_source_id}/query", payload)
            for page in data.get("results", []):
                codename = _page_title(page).strip()
                if not codename or _page_checkbox(page, archived_property):
                    continue
                accounts.append({
                    "id": page.get("id"),
                    "codename": codename,
                    "apple_card": _page_property_text(page, alias_property).strip(),
                })
            if not data.get("has_more"):
                accounts.reverse()
                return accounts
            cursor = data.get("next_cursor")

    def create_page(self, payload: dict) -> tuple[str | None, str | None]:
        """Create a page and return ``(page_id, url)`` from the response."""
        data = self._post("/pages", payload)
        return data.get("id"), data.get("url")

    def update_page(self, page_id: str, properties: dict) -> dict:
        """Patch a page's ``properties`` and return the response dict."""
        return self._patch(f"/pages/{page_id}", {"properties": properties})

    def _post(self, path: str, payload: dict) -> dict:
        return self._request("post", path, payload)

    def _patch(self, path: str, payload: dict) -> dict:
        return self._request("patch", path, payload)

    def _request(self, method: str, path: str, payload: dict) -> dict:
        started = time.perf_counter()
        try:
            resp = requests.request(
                method,
                f"{_API_ROOT}{path}",
                headers=self._headers,
                json=payload,
                timeout=_TIMEOUT,
            )
        except requests.RequestException as exc:
            _log.error("Notion %s %s network failure: %s", method.upper(), path, exc)
            raise NotionError(f"Could not reach Notion: {exc}") from exc

        latency_ms = (time.perf_counter() - started) * 1000
        try:
            data = resp.json()
        except ValueError:
            data = {}

        if resp.status_code >= 400:
            message = data.get("message") or resp.text or "request failed"
            _log.error(
                "Notion %s %s failed status=%s latency_ms=%.1f: %s",
                method.upper(),
                path,
                resp.status_code,
                latency_ms,
                message,
            )
            raise NotionError(f"Notion error: {message}", code=502)

        _log.debug(
            "Notion %s %s ok status=%s latency_ms=%.1f",
            method.upper(),
            path,
            resp.status_code,
            latency_ms,
        )
        return data


def _page_title(page: dict) -> str:
    """Return a page's plain-text title, found via its title-typed property."""
    for prop in page.get("properties", {}).values():
        if prop.get("type") == "title":
            return "".join(part.get("plain_text", "") for part in prop.get("title", []))
    return ""


def _page_property_text(page: dict, name: str) -> str:
    """Return the plain-text value of a named property, or ``""`` if absent.

    Handles the property shapes an alias might use: ``rich_text`` and ``title``
    concatenate their parts' ``plain_text``; ``select`` yields its option name.
    """
    prop = page.get("properties", {}).get(name)
    if not prop:
        return ""
    prop_type = prop.get("type")
    if prop_type in ("rich_text", "title"):
        return "".join(part.get("plain_text", "") for part in prop.get(prop_type, []))
    if prop_type == "select":
        select = prop.get("select") or {}
        return select.get("name", "")
    return ""


def _page_checkbox(page: dict, name: str) -> bool:
    """Return a named checkbox property's value, or ``False`` if absent."""
    prop = page.get("properties", {}).get(name)
    if not prop or prop.get("type") != "checkbox":
        return False
    return bool(prop.get("checkbox"))
