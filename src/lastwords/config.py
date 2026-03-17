from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class Settings:
    """Runtime configuration for a sync run."""

    blog_name: str
    blog_hostname: str
    post_state: str
    max_posts: int | None
    request_timeout: float
    state_file: Path
    consumer_key: str | None
    consumer_secret: str | None
    oauth_token: str | None
    oauth_secret: str | None

    @classmethod
    def from_env(
        cls,
        *,
        blog_name: str | None = None,
        blog_hostname: str | None = None,
        post_state: str | None = None,
        max_posts: int | None = None,
        request_timeout: float | None = None,
        state_file: Path | None = None,
    ) -> "Settings":
        """Build runtime settings from CLI overrides and environment variables.

        Args:
            blog_name: Optional Tumblr blog name override.
            blog_hostname: Optional public blog hostname override.
            post_state: Optional Tumblr post state override.
            max_posts: Optional limit for how many missing posts to process.
            request_timeout: Optional HTTP timeout override in seconds.
            state_file: Optional state file path override.

        Returns:
            Settings: The resolved settings object for the current run.
        """
        env_max_posts = os.getenv("LASTWORDS_MAX_POSTS")
        resolved_max_posts = max_posts
        if resolved_max_posts is None and env_max_posts:
            resolved_max_posts = int(env_max_posts)
        if resolved_max_posts is not None and resolved_max_posts <= 0:
            resolved_max_posts = None

        return cls(
            blog_name=blog_name or os.getenv("LASTWORDS_BLOG_NAME", "goodbyewarden"),
            blog_hostname=blog_hostname
            or os.getenv("LASTWORDS_BLOG_HOSTNAME", "lastwords.fyi"),
            post_state=post_state or os.getenv("LASTWORDS_POST_STATE", "published"),
            max_posts=resolved_max_posts,
            request_timeout=request_timeout
            if request_timeout is not None
            else float(os.getenv("LASTWORDS_REQUEST_TIMEOUT", "30")),
            state_file=state_file or Path(os.getenv("LASTWORDS_STATE_FILE", "data/state.json")),
            consumer_key=os.getenv("TUMBLR_CONSUMER_KEY"),
            consumer_secret=os.getenv("TUMBLR_CONSUMER_SECRET"),
            oauth_token=os.getenv("TUMBLR_OAUTH_TOKEN"),
            oauth_secret=os.getenv("TUMBLR_OAUTH_SECRET"),
        )

    def validate_posting_credentials(self) -> None:
        """Ensure all Tumblr credentials needed for posting are present.

        Args:
            None.

        Returns:
            None: This method returns successfully when all credentials exist.

        Raises:
            ValueError: Raised when one or more required Tumblr credentials are missing.
        """
        missing = [
            name
            for name, value in (
                ("TUMBLR_CONSUMER_KEY", self.consumer_key),
                ("TUMBLR_CONSUMER_SECRET", self.consumer_secret),
                ("TUMBLR_OAUTH_TOKEN", self.oauth_token),
                ("TUMBLR_OAUTH_SECRET", self.oauth_secret),
            )
            if not value
        ]
        if missing:
            joined = ", ".join(missing)
            raise ValueError(f"Missing Tumblr credentials: {joined}")
