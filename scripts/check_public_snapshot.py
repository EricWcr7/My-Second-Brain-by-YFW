"""Fail when a public source snapshot contains private-edition residue."""

from __future__ import annotations

import argparse
import re
import subprocess
from pathlib import Path


ALLOWED_BINARY_SUFFIXES = {".png", ".ttf", ".woff", ".woff2"}
FORBIDDEN_ROOTS = {
    "raw",
    "wiki",
    "." + "llm" + "wiki",
}
FORBIDDEN_PATH_PARTS = {
    "design" + "-qa",
    "sol" + "ver",
}
FORBIDDEN_CONTENT = {
    "private course identifier": "mat" + "237",
    "removed feature name": "sol" + "ver",
    "old product name": "my second " + "brain",
    "old repository name": "my-second-brain-" + "yfw",
    "private account path": "yifan" + "wang",
    "university domain": "uto" + "ronto",
    "macOS home path": "/" + "users/",
    "Windows home path": "c:\\" + "users\\",
    "private source name": "za" + "man",
    "removed provider type": "chat" + "message",
    "removed provider result": "chat" + "result",
    "removed metadata field": "reasoning" + "_summary",
}
SECRET_PATTERNS = {
    "OpenAI-style key": re.compile(rb"sk-[A-Za-z0-9_-]{20,}"),
    "AWS access key": re.compile(rb"AKIA[0-9A-Z]{16}"),
    "GitHub token": re.compile(rb"(?:gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{30,})"),
    "private key block": re.compile(rb"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
}


def source_files(root: Path) -> list[Path]:
    """Return tracked files in a checkout, or all files in an exported tree."""
    probe = subprocess.run(
        ["git", "-C", str(root), "rev-parse", "--is-inside-work-tree"],
        capture_output=True,
        text=True,
        check=False,
    )
    if probe.returncode == 0:
        listed = subprocess.run(
            [
                "git",
                "-C",
                str(root),
                "ls-files",
                "--cached",
                "--others",
                "--exclude-standard",
                "-z",
            ],
            capture_output=True,
            check=True,
        ).stdout
        return [root / item.decode() for item in listed.split(b"\0") if item]
    return sorted(path for path in root.rglob("*") if path.is_file() and ".git" not in path.parts)


def audit(root: Path) -> list[str]:
    failures: list[str] = []
    for path in source_files(root):
        if not path.exists():
            continue
        relative = path.relative_to(root)
        lowered_parts = tuple(part.lower() for part in relative.parts)
        if lowered_parts and lowered_parts[0] in FORBIDDEN_ROOTS:
            failures.append(f"forbidden root: {relative}")
        if any(token in part for part in lowered_parts for token in FORBIDDEN_PATH_PARTS):
            failures.append(f"forbidden path: {relative}")
        if path.suffix.lower() == ".pdf":
            failures.append(f"PDF must not be published: {relative}")

        data = path.read_bytes()
        lowered = data.lower()
        for label, marker in FORBIDDEN_CONTENT.items():
            if marker.encode() in lowered:
                failures.append(f"{label}: {relative}")
        for label, pattern in SECRET_PATTERNS.items():
            if pattern.search(data):
                failures.append(f"possible {label}: {relative}")
        if b"\0" in data and path.suffix.lower() not in ALLOWED_BINARY_SUFFIXES:
            failures.append(f"unexpected binary file: {relative}")
    return sorted(set(failures))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("root", nargs="?", type=Path, default=Path.cwd())
    args = parser.parse_args()
    root = args.root.resolve()
    failures = audit(root)
    if failures:
        print("Public snapshot audit failed:")
        for failure in failures:
            print(f"- {failure}")
        return 1
    print(f"Public snapshot audit passed ({len(source_files(root))} files checked).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
