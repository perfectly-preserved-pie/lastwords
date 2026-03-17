from __future__ import annotations

import json
import re
from html import unescape
from typing import Any

import pytumblr
import requests
from bs4 import BeautifulSoup

from lastwords.config import Settings
from lastwords.models import ExecutionRecord, TumblrQuoteReference

READ_API_PAGE_SIZE = 50
EXECUTION_TAG_PATTERN = re.compile(r"\bExecution\s+(\d+)\b", re.IGNORECASE)


def parse_public_read_json(body: str) -> dict[str, Any]:
    """Parse Tumblr's legacy JavaScript-wrapped read API response.

    Args:
        body: Raw response body from the Tumblr read API.

    Returns:
        dict[str, Any]: Parsed JSON payload with the wrapper removed.
    """
    payload = body.strip()
    prefix = "var tumblr_api_read = "
    if payload.startswith(prefix):
        payload = payload[len(prefix) :]
    if payload.endswith(";"):
        payload = payload[:-1]
    return json.loads(payload)


def extract_statement_url_from_quote_source(source_html: str) -> str | None:
    """Extract the TDCJ statement URL from Tumblr quote source HTML.

    Args:
        source_html: HTML stored in Tumblr's quote source field.

    Returns:
        str | None: The extracted last-statement URL, or `None` when no links are present.
    """
    soup = BeautifulSoup(unescape(source_html), "html.parser")
    links = soup.find_all("a")
    if not links:
        return None

    for link in links:
        if "last statement" in link.get_text(" ", strip=True).lower():
            return link.get("href")
    return links[-1].get("href")


def extract_execution_from_tags(tags: list[str]) -> int | None:
    """Parse the execution number from a Tumblr tag list.

    Args:
        tags: Tumblr tags attached to a quote post.

    Returns:
        int | None: The parsed execution number, or `None` when not found.
    """
    for tag in tags:
        match = EXECUTION_TAG_PATTERN.search(tag)
        if match:
            return int(match.group(1))
    return None


def fetch_existing_quotes(
    session: requests.Session,
    *,
    blog_hostname: str,
    timeout: float,
) -> list[TumblrQuoteReference]:
    """Fetch all existing public quote posts from the Tumblr read API.

    Args:
        session: Requests session used for HTTP requests.
        blog_hostname: Public hostname for the Tumblr blog.
        timeout: HTTP timeout in seconds.

    Returns:
        list[TumblrQuoteReference]: Public quote references used for deduplication.
    """
    references: list[TumblrQuoteReference] = []
    start = 0
    total: int | None = None

    while total is None or start < total:
        url = (
            f"https://{blog_hostname}/api/read/json?type=quote"
            f"&num={READ_API_PAGE_SIZE}&start={start}"
        )
        response = session.get(url, timeout=timeout)
        response.raise_for_status()
        payload = parse_public_read_json(response.text)

        total = int(payload.get("posts-total", 0))
        posts = payload.get("posts", [])
        if not posts:
            break

        for post in posts:
            statement_url = extract_statement_url_from_quote_source(post.get("quote-source", ""))
            if statement_url is None:
                continue

            references.append(
                TumblrQuoteReference(
                    statement_url=statement_url,
                    execution=extract_execution_from_tags(post.get("tags", [])),
                    post_id=post.get("id"),
                )
            )

        start += len(posts)

    return references


class TumblrPoster:
    """Small Tumblr client wrapper for creating quote posts."""

    def __init__(self, settings: Settings) -> None:
        """Create a Tumblr poster from resolved application settings.

        Args:
            settings: Resolved runtime settings with Tumblr credentials.

        Returns:
            None: The poster is initialized in place.
        """
        settings.validate_posting_credentials()
        self.blog_name = settings.blog_name
        self.post_state = settings.post_state
        self.client = pytumblr.TumblrRestClient(
            settings.consumer_key,
            settings.consumer_secret,
            settings.oauth_token,
            settings.oauth_secret,
        )

    def create_quote(self, record: ExecutionRecord) -> dict[str, Any]:
        """Create a quote post on Tumblr for a single execution record.

        Args:
            record: Execution record containing the quote text and source metadata.

        Returns:
            dict[str, Any]: Raw Tumblr API response for the created quote.

        Raises:
            ValueError: Raised when the record does not include statement text.
        """
        if record.statement_text is None:
            raise ValueError("Cannot create a Tumblr quote without statement text.")

        response = self.client.create_quote(
            self.blog_name,
            state=self.post_state,
            quote=record.statement_text,
            source=build_quote_source(record),
            tags=build_tags(record),
        )
        if not isinstance(response, dict):
            raise ValueError("Unexpected Tumblr API response shape.")
        return response


def build_quote_source(record: ExecutionRecord) -> str:
    """Build the HTML source field attached to a Tumblr quote post.

    Args:
        record: Execution record used to populate the source metadata.

    Returns:
        str: HTML source text linking back to the TDCJ offender and statement pages.
    """
    age = f"{record.age} years old. " if record.age is not None else ""
    date_text = (
        f"{record.execution_date.month}/"
        f"{record.execution_date.day}/"
        f"{record.execution_date.year}"
    )
    return (
        f"{record.full_name}. {age}Executed {date_text}. "
        f"<br/> <small> "
        f"<a href=\"{record.offender_url}\">Offender Information</a> "
        f"<br/> "
        f"<a href=\"{record.statement_url}\">Last Statement</a> "
        f"</small>"
    )


def build_tags(record: ExecutionRecord) -> list[str]:
    """Build the Tumblr tags attached to a quote post.

    Args:
        record: Execution record used to generate tags.

    Returns:
        list[str]: Tags for the created Tumblr quote post.
    """
    return [record.full_name, f"Execution {record.execution}", "TDCJ"]
