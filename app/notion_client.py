"""Thin Notion API wrapper (requests-based).

Only the pieces the bridge needs: resolve a page id from its title
(:meth:`NotionClient.query_by_name`), create a transaction page
(:meth:`NotionClient.create_page`), and patch an existing page
(:meth:`NotionClient.update_page`, used from Phase 3). All calls target the
2025-09-03 API, where pages are parented by ``data_source_id`` and lookup
tables are queried at ``/v1/data_sources/{id}/query``.
"""

import requests

_API_ROOT = "https://api.notion.com/v1"
# PythonAnywhere's free tier is slow to reach out; give Notion room to answer.
_TIMEOUT = 15


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
        try:
            resp = requests.request(
                method,
                f"{_API_ROOT}{path}",
                headers=self._headers,
                json=payload,
                timeout=_TIMEOUT,
            )
        except requests.RequestException as exc:
            raise NotionError(f"Could not reach Notion: {exc}") from exc

        try:
            data = resp.json()
        except ValueError:
            data = {}

        if resp.status_code >= 400:
            message = data.get("message") or resp.text or "request failed"
            raise NotionError(f"Notion error: {message}", code=502)
        return data


def _page_title(page: dict) -> str:
    """Return a page's plain-text title, found via its title-typed property."""
    for prop in page.get("properties", {}).values():
        if prop.get("type") == "title":
            return "".join(part.get("plain_text", "") for part in prop.get("title", []))
    return ""
