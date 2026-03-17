from __future__ import annotations

from datetime import datetime
from typing import Iterable
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

from lastwords.models import ExecutionRecord

EXECUTIONS_URL = "https://www.tdcj.texas.gov/death_row/dr_executed_offenders.html"
NON_STATEMENT_MARKERS = {
    "",
    "none",
    "none.",
    "no",
    "no.",
    "no statement given.",
    "no statement was made.",
    "no last statement.",
    "this inmate declined to make a last statement.",
    "no, i have no final statement.",
    "(written statement)",
    "spoken: no",
    "spoken: no.",
}


def normalize_whitespace(text: str) -> str:
    """Collapse repeated whitespace into single spaces.

    Args:
        text: Raw text that may contain repeated spaces or line breaks.

    Returns:
        str: Normalized text with compact whitespace.
    """
    return " ".join(text.split())


def normalize_statement_url(url: str) -> str:
    """Normalize a statement URL for set membership and comparisons.

    Args:
        url: The raw statement URL.

    Returns:
        str: The normalized statement URL without trailing slashes.
    """
    return url.strip().rstrip("/")


def parse_executions_html(html_text: str, *, base_url: str = EXECUTIONS_URL) -> list[ExecutionRecord]:
    """Parse the TDCJ executed-offenders table into normalized records.

    Args:
        html_text: HTML body from the TDCJ executed-offenders page.
        base_url: Base URL used to resolve relative offender and statement links.

    Returns:
        list[ExecutionRecord]: Parsed execution records found in the table.

    Raises:
        ValueError: Raised when the expected executed-inmates table is missing.
    """
    soup = BeautifulSoup(html_text, "html.parser")
    table = soup.find("table")
    if table is None:
        raise ValueError("Could not find the executed inmates table on the TDCJ page.")

    records: list[ExecutionRecord] = []
    for row in table.find_all("tr")[1:]:
        cells = row.find_all("td")
        if len(cells) < 10:
            continue

        links = row.find_all("a")
        if len(links) < 2:
            continue

        execution_text = normalize_whitespace(cells[0].get_text())
        age_text = normalize_whitespace(cells[6].get_text())
        date_text = normalize_whitespace(cells[7].get_text())

        records.append(
            ExecutionRecord(
                execution=int(execution_text),
                last_name=normalize_whitespace(cells[3].get_text()),
                first_name=normalize_whitespace(cells[4].get_text()),
                tdcj_number=normalize_whitespace(cells[5].get_text()),
                age=int(age_text) if age_text.isdigit() else None,
                execution_date=datetime.strptime(date_text, "%m/%d/%Y").date(),
                race=normalize_whitespace(cells[8].get_text()),
                county=normalize_whitespace(cells[9].get_text()),
                offender_url=urljoin(base_url, links[0]["href"]),
                statement_url=urljoin(base_url, links[1]["href"]),
            )
        )

    return records


def fetch_executions(session: requests.Session, *, timeout: float) -> list[ExecutionRecord]:
    """Fetch and parse the current TDCJ executed-offenders page.

    Args:
        session: Requests session used for HTTP requests.
        timeout: HTTP timeout in seconds.

    Returns:
        list[ExecutionRecord]: Parsed execution records from the live TDCJ page.
    """
    response = session.get(EXECUTIONS_URL, timeout=timeout)
    response.raise_for_status()
    return parse_executions_html(response.text, base_url=response.url)


def parse_statement_html(html_text: str) -> str | None:
    """Extract the last-statement text from a TDCJ offender page.

    Args:
        html_text: HTML body from a TDCJ last-statement page.

    Returns:
        str | None: The normalized statement text, or `None` when TDCJ reports no statement.

    Raises:
        ValueError: Raised when the expected last-statement marker is missing.
    """
    soup = BeautifulSoup(html_text, "html.parser")
    label = next(
        (
            tag
            for tag in soup.find_all("p")
            if normalize_whitespace(tag.get_text()) == "Last Statement:"
        ),
        None,
    )
    if label is None:
        raise ValueError("Could not find the last statement marker on the TDCJ page.")

    paragraphs: list[str] = []
    for sibling in label.find_next_siblings():
        if sibling.name != "p":
            break
        paragraph = normalize_whitespace(sibling.get_text(" ", strip=True))
        if paragraph:
            paragraphs.append(paragraph)

    statement = normalize_whitespace(" ".join(paragraphs))
    if statement.lower() in NON_STATEMENT_MARKERS:
        return None
    return statement or None


def fetch_statement_text(
    session: requests.Session,
    statement_url: str,
    *,
    timeout: float,
) -> str | None:
    """Fetch and parse the statement text for a single execution.

    Args:
        session: Requests session used for HTTP requests.
        statement_url: URL of the TDCJ last-statement page.
        timeout: HTTP timeout in seconds.

    Returns:
        str | None: The normalized statement text, or `None` when no statement exists.
    """
    response = session.get(statement_url, timeout=timeout)
    response.raise_for_status()
    return parse_statement_html(response.text)


def sort_oldest_first(records: Iterable[ExecutionRecord]) -> list[ExecutionRecord]:
    """Sort execution records chronologically from oldest to newest.

    Args:
        records: Iterable of execution records to sort.

    Returns:
        list[ExecutionRecord]: Records ordered by execution date and execution number.
    """
    return sorted(records, key=lambda record: (record.execution_date, record.execution))
