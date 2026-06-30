from __future__ import annotations

import argparse
import os
import sys
from dataclasses import replace
from datetime import datetime, UTC
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

import requests
from loguru import logger
from requests_oauthlib import OAuth1Session

from lastwords.config import Settings
from lastwords.state import load_state, save_state
from lastwords.tdcj import (
    fetch_executions,
    fetch_statement_text,
    normalize_statement_url,
    sort_oldest_first,
)
from lastwords.tumblr import TumblrPoster, fetch_existing_quotes

TUMBLR_REQUEST_TOKEN_URL = "https://www.tumblr.com/oauth/request_token"
TUMBLR_AUTHORIZE_URL = "https://www.tumblr.com/oauth/authorize"
TUMBLR_ACCESS_TOKEN_URL = "https://www.tumblr.com/oauth/access_token"
DEFAULT_TUMBLR_CALLBACK_URL = "https://lastwords.fyi/"


def build_parser() -> argparse.ArgumentParser:
    """Build the command-line parser for the application.

    Returns:
        argparse.ArgumentParser: Configured top-level parser with subcommands.
    """
    parser = argparse.ArgumentParser(
        prog="lastwords",
        description="Sync TDCJ last statements to Tumblr.",
    )
    subparsers = parser.add_subparsers(dest="command")

    sync_parser = subparsers.add_parser(
        "sync",
        help="Fetch TDCJ executions, compare against Tumblr, and post missing quotes.",
    )
    sync_parser.add_argument("--dry-run", action="store_true", help="Do not create Tumblr posts.")
    sync_parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Maximum number of missing statements to process this run.",
    )
    sync_parser.add_argument(
        "--state-file",
        type=Path,
        default=None,
        help="Override the JSON state file path.",
    )
    sync_parser.add_argument("--blog-name", default=None, help="Override the Tumblr blog name.")
    sync_parser.add_argument(
        "--blog-hostname",
        default=None,
        help="Override the public Tumblr hostname used for archive reads.",
    )
    sync_parser.add_argument(
        "--post-state",
        default=None,
        choices=["published", "queue", "draft", "private"],
        help="Tumblr post state.",
    )
    sync_parser.add_argument(
        "--request-timeout",
        type=float,
        default=None,
        help="HTTP timeout in seconds.",
    )

    auth_parser = subparsers.add_parser(
        "tumblr-auth",
        help="Generate Tumblr OAuth token secrets from a consumer key and secret.",
    )
    auth_parser.add_argument(
        "--consumer-key",
        default=None,
        help="Tumblr OAuth consumer key. Defaults to TUMBLR_CONSUMER_KEY.",
    )
    auth_parser.add_argument(
        "--consumer-secret",
        default=None,
        help="Tumblr OAuth consumer secret. Defaults to TUMBLR_CONSUMER_SECRET.",
    )
    auth_parser.add_argument(
        "--verifier",
        default=None,
        help="OAuth verifier, or the full redirected callback URL from Tumblr.",
    )
    auth_parser.add_argument(
        "--callback-url",
        default=None,
        help=(
            "OAuth callback URL registered on the Tumblr application. Defaults "
            "to TUMBLR_CALLBACK_URL or https://lastwords.fyi/."
        ),
    )

    return parser


def configure_logger() -> None:
    """Configure the application logger for CLI output.

    Returns:
        None: The global logger is configured in place.
    """
    logger.remove()
    logger.add(sys.stderr, format="{message}")


def main(argv: list[str] | None = None) -> int:
    """Run the command-line entrypoint.

    Args:
        argv: Optional list of CLI arguments to parse instead of `sys.argv`.

    Returns:
        int: Process exit code.
    """
    configure_logger()
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command in (None, "sync"):
        return run_sync(args)

    if args.command == "tumblr-auth":
        return run_tumblr_auth(args)

    parser.error(f"Unknown command: {args.command}")
    return 2


def run_tumblr_auth(args: argparse.Namespace) -> int:
    """Run Tumblr's OAuth 1.0a authorization flow.

    Args:
        args: Parsed command-line arguments for the auth command.

    Returns:
        int: Process exit code for the authorization operation.
    """
    consumer_key = args.consumer_key or os.getenv("TUMBLR_CONSUMER_KEY")
    consumer_secret = args.consumer_secret or os.getenv("TUMBLR_CONSUMER_SECRET")
    callback_url = (
        args.callback_url
        or os.getenv("TUMBLR_CALLBACK_URL")
        or DEFAULT_TUMBLR_CALLBACK_URL
    )
    missing = [
        name
        for name, value in (
            ("TUMBLR_CONSUMER_KEY", consumer_key),
            ("TUMBLR_CONSUMER_SECRET", consumer_secret),
        )
        if not value
    ]
    if missing:
        logger.error("Missing Tumblr app credentials: {}", ", ".join(missing))
        return 1

    request_session = OAuth1Session(
        consumer_key,
        client_secret=consumer_secret,
        callback_uri=callback_url,
    )
    request_token = request_session.fetch_request_token(TUMBLR_REQUEST_TOKEN_URL)
    resource_owner_key = request_token.get("oauth_token")
    resource_owner_secret = request_token.get("oauth_token_secret")
    if not resource_owner_key or not resource_owner_secret:
        logger.error("Tumblr did not return a request token.")
        return 1

    authorization_url = request_session.authorization_url(TUMBLR_AUTHORIZE_URL)
    logger.info("Open this URL while logged into the Tumblr account that owns the blog:")
    logger.info(authorization_url)

    verifier_input = args.verifier or input(
        "Paste the OAuth verifier or full redirected callback URL from Tumblr: "
    ).strip()
    verifier = parse_oauth_verifier(verifier_input)
    if not verifier:
        logger.error("No OAuth verifier provided.")
        return 1

    access_session = OAuth1Session(
        consumer_key,
        client_secret=consumer_secret,
        resource_owner_key=resource_owner_key,
        resource_owner_secret=resource_owner_secret,
        verifier=verifier,
    )
    access_token = access_session.fetch_access_token(TUMBLR_ACCESS_TOKEN_URL)
    oauth_token = access_token.get("oauth_token")
    oauth_secret = access_token.get("oauth_token_secret")
    if not oauth_token or not oauth_secret:
        logger.error("Tumblr did not return an access token and secret.")
        return 1

    logger.info("Add these as GitHub repository secrets:")
    logger.info("TUMBLR_OAUTH_TOKEN={}", oauth_token)
    logger.info("TUMBLR_OAUTH_SECRET={}", oauth_secret)
    return 0


def parse_oauth_verifier(value: str) -> str:
    """Extract an OAuth verifier from a raw verifier or redirected URL.

    Args:
        value: Raw verifier text or the full callback URL from Tumblr.

    Returns:
        str: The extracted verifier, or an empty string when not present.
    """
    value = value.strip()
    if not value:
        return ""
    parsed = urlparse(value)
    if parsed.query:
        query = parse_qs(parsed.query)
        verifier = query.get("oauth_verifier", [""])[0]
        if verifier:
            return verifier
    return value


def run_sync(args: argparse.Namespace) -> int:
    """Execute the TDCJ-to-Tumblr sync flow.

    Args:
        args: Parsed command-line arguments for the sync command.

    Returns:
        int: Process exit code for the sync operation.
    """
    settings = Settings.from_env(
        blog_name=args.blog_name,
        blog_hostname=args.blog_hostname,
        post_state=args.post_state,
        max_posts=args.limit,
        request_timeout=args.request_timeout,
        state_file=args.state_file,
    )
    state = load_state(settings.state_file)
    state["blog_name"] = settings.blog_name
    state["blog_hostname"] = settings.blog_hostname

    session = requests.Session()
    session.headers.update({"User-Agent": "lastwords/0.2.0 (+https://lastwords.fyi/)"})

    logger.info("Fetching executed offenders from TDCJ...")
    tdcj_records = sort_oldest_first(fetch_executions(session, timeout=settings.request_timeout))
    latest_tdcj_execution = max((record.execution for record in tdcj_records), default=None)

    logger.info("Reading the public Tumblr archive...")
    public_quotes = fetch_existing_quotes(
        session,
        blog_hostname=settings.blog_hostname,
        timeout=settings.request_timeout,
    )
    public_statement_urls = {
        normalize_statement_url(reference.statement_url) for reference in public_quotes
    }
    state_statement_urls = {
        normalize_statement_url(url) for url in state.get("known_statement_urls", [])
    }
    ignored_statement_urls = {
        normalize_statement_url(url) for url in state.get("ignored_statement_urls", [])
    }
    known_statement_urls = public_statement_urls | state_statement_urls
    latest_public_execution = max(
        (reference.execution for reference in public_quotes if reference.execution is not None),
        default=None,
    )

    pending_records = [
        record
        for record in tdcj_records
        if normalize_statement_url(record.statement_url) not in known_statement_urls
        and normalize_statement_url(record.statement_url) not in ignored_statement_urls
    ]
    if settings.max_posts is not None:
        pending_records = pending_records[: settings.max_posts]

    logger.info("Found {} missing statement(s) to process.", len(pending_records))

    posted: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    would_post_count = 0
    poster: TumblrPoster | None = None
    if pending_records and not args.dry_run:
        poster = TumblrPoster(settings)
        logger.info("Checking Tumblr credentials...")
        poster.validate_authentication()

    for record in pending_records:
        logger.info("Fetching statement text for execution {}...", record.execution)
        statement_text = fetch_statement_text(
            session,
            record.statement_url,
            timeout=settings.request_timeout,
        )
        if statement_text is None:
            logger.info(
                "Skipping execution {} because TDCJ has no statement text.",
                record.execution,
            )
            ignored_statement_urls.add(normalize_statement_url(record.statement_url))
            skipped.append(
                {
                    "execution": record.execution,
                    "name": record.full_name,
                    "statement_url": record.statement_url,
                    "reason": "no_statement",
                }
            )
            continue

        enriched_record = replace(record, statement_text=statement_text)
        if args.dry_run:
            logger.info(
                "Dry run: would post execution {} for {}.",
                record.execution,
                record.full_name,
            )
            would_post_count += 1
            continue
        else:
            if poster is None:
                poster = TumblrPoster(settings)
            logger.info("Posting execution {} for {}...", record.execution, record.full_name)
            response = poster.create_quote(enriched_record)
            response_id = response.get("id")

        known_statement_urls.add(normalize_statement_url(record.statement_url))
        posted.append(
            {
                "execution": record.execution,
                "name": record.full_name,
                "statement_url": record.statement_url,
                "offender_url": record.offender_url,
                "execution_date": record.execution_date.isoformat(),
                "tumblr_post_id": response_id,
            }
        )

    now = datetime.now(UTC).isoformat()
    state["known_statement_urls"] = sorted(known_statement_urls)
    state["ignored_statement_urls"] = sorted(ignored_statement_urls)
    state["last_run_at"] = now
    state["latest_tdcj_execution_seen"] = latest_tdcj_execution
    state["latest_public_execution_seen"] = latest_public_execution
    state["last_result"] = {
        "dry_run": args.dry_run,
        "pending_count": len(pending_records),
        "would_post_count": would_post_count,
        "posted_count": len(posted),
        "skipped_count": len(skipped),
    }
    if posted:
        state["most_recent_post"] = posted[-1]
    state["recent_posts"] = (state.get("recent_posts", []) + posted)[-25:]
    state["recent_skips"] = (state.get("recent_skips", []) + skipped)[-25:]

    save_state(settings.state_file, state)

    logger.success("Sync complete.")
    logger.info("Latest TDCJ execution seen: {}", latest_tdcj_execution)
    logger.info("Latest public Tumblr execution seen: {}", latest_public_execution)
    if args.dry_run:
        logger.info("Would post this run: {}", would_post_count)
    logger.info("Posted this run: {}", len(posted))
    logger.info("Skipped this run: {}", len(skipped))
    logger.info("State written to {}", settings.state_file)
    return 0
