from __future__ import annotations

from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True, slots=True)
class ExecutionRecord:
    """Normalized execution data scraped from TDCJ."""

    execution: int
    first_name: str
    last_name: str
    tdcj_number: str
    age: int | None
    execution_date: date
    race: str
    county: str
    offender_url: str
    statement_url: str
    statement_text: str | None = None

    @property
    def full_name(self) -> str:
        """Build the display name used in logs, tags, and Tumblr posts.

        Returns:
            str: The execution record's combined first and last name.
        """
        return f"{self.first_name} {self.last_name}".strip()


@dataclass(frozen=True, slots=True)
class TumblrQuoteReference:
    """Minimal Tumblr quote metadata used for deduplication."""

    statement_url: str
    execution: int | None
    post_id: str | None
