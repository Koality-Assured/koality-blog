#!/usr/bin/env python3
"""Validate front matter metadata in all blog post markdown files."""

from __future__ import annotations

import re
import sys
from pathlib import Path

REQUIRED_FIELDS = {
    "title": str,
    "deck": str,
    "date": str,
    "domain": str,
    "author": str,
    "reading_time": str,
    "canonical_url": str,
}

OPTIONAL_FIELDS = {
    "related_whitepaper": str,
}


def parse_frontmatter(content: str) -> dict[str, str]:
    """Parse YAML frontmatter delimited by '---' without third-party dependencies."""
    lines = content.splitlines()
    if not lines or lines[0].strip() != "---":
        raise ValueError("File does not begin with '---' frontmatter delimiter")

    end_idx = -1
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            end_idx = i
            break

    if end_idx == -1:
        raise ValueError("No closing '---' frontmatter delimiter found")

    frontmatter_lines = lines[1:end_idx]
    data: dict[str, str] = {}
    for line in frontmatter_lines:
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if ":" not in line:
            raise ValueError(f"Malformed frontmatter line: {line!r}")
        key, value = line.split(":", 1)
        key = key.strip()
        value = value.strip()
        if (value.startswith('"') and value.endswith('"')) or (
            value.startswith("'") and value.endswith("'")
        ):
            value = value[1:-1]
        data[key] = value

    return data


def validate_post(post_path: Path) -> list[str]:
    """Validate a single POST.md file."""
    errors: list[str] = []
    try:
        content = post_path.read_text(encoding="utf-8")
    except Exception as exc:
        return [f"Could not read {post_path}: {exc}"]

    try:
        data = parse_frontmatter(content)
    except ValueError as exc:
        return [f"Frontmatter parse error in {post_path}: {exc}"]

    for field, expected_type in REQUIRED_FIELDS.items():
        if field not in data:
            errors.append(f"{post_path}: Missing required field {field!r}")
        elif not data[field]:
            errors.append(f"{post_path}: Field {field!r} must not be empty")

    if "date" in data:
        # Expected YYYY-MM-DD
        if not re.match(r"^\d{4}-\d{2}-\d{2}$", data["date"]):
            errors.append(f"{post_path}: Date must be in YYYY-MM-DD format, got {data['date']!r}")

    if "canonical_url" in data:
        if not data["canonical_url"].startswith("https://ketron.dev/blog/"):
            errors.append(
                f"{post_path}: canonical_url must start with 'https://ketron.dev/blog/', got {data['canonical_url']!r}"
            )

    if "reading_time" in data:
        if not re.search(r"\bread\b", data["reading_time"]):
            errors.append(
                f"{post_path}: reading_time must contain 'read' (e.g. '4 min read'), got {data['reading_time']!r}"
            )

    return errors


def main() -> int:
    repo_root = Path(__file__).resolve().parent.parent
    posts_dir = repo_root / "posts"
    if not posts_dir.exists():
        print(f"Error: posts directory not found at {posts_dir}", file=sys.stderr)
        return 1

    post_files = list(posts_dir.rglob("POST.md"))
    if not post_files:
        print("Warning: No POST.md files found to validate.", file=sys.stderr)
        return 0

    total_errors: list[str] = []
    for post in sorted(post_files):
        errors = validate_post(post)
        if errors:
            total_errors.extend(errors)
        else:
            print(f"OK: {post.relative_to(repo_root)}")

    if total_errors:
        print(f"\nFrontmatter validation failed with {len(total_errors)} errors:", file=sys.stderr)
        for err in total_errors:
            print(f"  - {err}", file=sys.stderr)
        return 1

    print(f"\nAll {len(post_files)} posts passed frontmatter validation.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
