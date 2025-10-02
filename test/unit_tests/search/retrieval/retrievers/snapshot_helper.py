# Copyright 2019-2025 SURF, GÉANT.
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""SQL snapshot testing helper for retriever tests.

Usage:
    # Record mode (generates/updates snapshots):
    pytest test/unit_tests/search/retrieval/retrievers/test_retrievers.py --record

    # Normal mode (asserts against snapshots):
    pytest test/unit_tests/search/retrieval/retrievers/test_retrievers.py
"""

import json
from pathlib import Path

from structlog import get_logger

logger = get_logger(__name__)


def get_snapshot_path() -> Path:
    """Get path to the SQL snapshots file."""
    return Path(__file__).parent / "sql_snapshots.json"


def load_snapshots() -> dict[str, str]:
    """Load SQL snapshots from JSON file."""
    snapshot_file = get_snapshot_path()
    if not snapshot_file.exists():
        return {}

    with open(snapshot_file, "r") as f:
        return json.load(f)


def save_snapshots(snapshots: dict[str, str]) -> None:
    """Save SQL snapshots to JSON file with formatting."""
    snapshot_file = get_snapshot_path()

    with open(snapshot_file, "w") as f:
        json.dump(snapshots, f, indent=2, sort_keys=True)


def assert_sql_matches_snapshot(test_name: str, sql: str, request) -> None:
    """Assert SQL matches stored snapshot or record new snapshot.

    In record mode (--record flag), this function saves the SQL as a new snapshot.
    In normal mode, it compares the SQL against the stored snapshot and raises
    an AssertionError if they differ.

    Args:
        test_name (str): Unique name for this test (e.g., "StructuredRetriever.test_basic").
        sql (str): The SQL string to compare. Exact format is preserved.
        request: Pytest request fixture to access CLI options.

    Raises:
        AssertionError: If snapshot doesn't exist or SQL doesn't match stored snapshot.
    """
    record_mode = request.config.getoption("--record", default=False)

    snapshots = load_snapshots()

    if record_mode:
        # Record/update the snapshot
        snapshots[test_name] = sql
        save_snapshots(snapshots)
        logger.warning(f"\n✓ Recorded snapshot for: {test_name}")
    else:
        if test_name not in snapshots:
            raise AssertionError(
                f"No snapshot found for '{test_name}'.\n"
                f"Run with --record to create it:\n"
                f"  pytest test/unit_tests/search/retrieval/retrievers/test_retrievers.py --record"
            )

        expected_sql = snapshots[test_name]

        if sql != expected_sql:
            raise AssertionError(
                f"SQL snapshot mismatch for '{test_name}':\n\n"
                f"Expected:\n{expected_sql}\n\n"
                f"Got:\n{sql}\n\n"
                f"To update snapshot, run:\n"
                f"  pytest test/unit_tests/search/retrieval/retrievers/test_retrievers.py --record"
            )
