from __future__ import annotations

import re
from pathlib import Path


VERSIONS_DIR = Path(__file__).resolve().parents[1] / "app" / "db" / "migrations" / "versions"
REVISION_PATTERN = re.compile(r'^revision:\s*str\s*=\s*"([^"]+)"', re.MULTILINE)
DOWN_REVISION_PATTERN = re.compile(
    r'^down_revision:\s*Union\[str,\s*None\]\s*=\s*(?:"([^"]+)"|None)', re.MULTILINE
)


def _migration_pairs() -> list[tuple[str, str | None]]:
    pairs: list[tuple[str, str | None]] = []
    for path in sorted(VERSIONS_DIR.glob("*.py")):
        content = path.read_text()
        revision_match = REVISION_PATTERN.search(content)
        down_revision_match = DOWN_REVISION_PATTERN.search(content)

        assert revision_match, f"missing revision in {path.name}"
        assert down_revision_match, f"missing down_revision in {path.name}"

        pairs.append((revision_match.group(1), down_revision_match.group(1)))

    assert pairs, "no migrations found"
    return pairs


def test_migrations_have_single_linear_head() -> None:
    pairs = _migration_pairs()

    revisions = [revision for revision, _ in pairs]
    assert len(set(revisions)) == len(revisions), "duplicate Alembic revision IDs detected"

    parent_by_revision = dict(pairs)
    children: dict[str, list[str]] = {}
    roots: list[str] = []

    for revision, parent in pairs:
        if parent is None:
            roots.append(revision)
            continue
        children.setdefault(parent, []).append(revision)

    assert len(roots) == 1, f"expected exactly one root migration, got: {roots}"

    branch_points = {parent: kids for parent, kids in children.items() if len(kids) > 1}
    assert not branch_points, f"found migration branches: {branch_points}"

    heads = [revision for revision in revisions if revision not in children]
    assert len(heads) == 1, f"expected exactly one migration head, got: {heads}"

    # Walk from root and ensure we can visit every revision once in order.
    visited: list[str] = []
    current = roots[0]
    while True:
        visited.append(current)
        next_revisions = children.get(current, [])
        if not next_revisions:
            break
        current = next_revisions[0]

    assert len(visited) == len(revisions), (
        "migration graph is disconnected or cyclic; "
        f"visited={visited}, all={sorted(revisions)}"
    )

    # Sanity-check no self-references.
    for revision, parent in pairs:
        assert revision != parent, f"migration {revision} cannot depend on itself"
        assert parent is None or parent in parent_by_revision, (
            f"migration {revision} points to unknown down_revision {parent}"
        )
