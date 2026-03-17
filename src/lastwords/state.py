from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any

StateData = dict[str, Any]

DEFAULT_STATE: StateData = {
    "schema_version": 1,
    "blog_name": "goodbyewarden",
    "blog_hostname": "lastwords.fyi",
    "known_statement_urls": [],
    "ignored_statement_urls": [],
    "last_run_at": None,
    "last_result": {
        "dry_run": True,
        "pending_count": 0,
        "would_post_count": 0,
        "posted_count": 0,
        "skipped_count": 0,
    },
    "latest_tdcj_execution_seen": None,
    "latest_public_execution_seen": None,
    "most_recent_post": None,
    "recent_posts": [],
    "recent_skips": [],
}


def load_state(path: Path) -> StateData:
    """Load the persisted sync state from disk.

    Args:
        path: Path to the JSON state file.

    Returns:
        StateData: The merged default and persisted state data.
    """
    state: StateData = deepcopy(DEFAULT_STATE)
    if path.exists():
        raw_state: StateData = json.loads(path.read_text(encoding="utf-8"))
        state.update(raw_state)
    return state


def save_state(path: Path, state: StateData) -> None:
    """Write the current sync state to disk as formatted JSON.

    Args:
        path: Path to the JSON state file.
        state: State data to persist.

    Returns:
        None: The state file is written in place.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(state, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
