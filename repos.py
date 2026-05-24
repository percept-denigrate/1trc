#!/usr/bin/env python3
"""
1trc - One Terabyte to Rebuild Civilization
Repo cloning script: reads repos.txt and clones each repo into its
corresponding directory hierarchy.

Usage:
    python clone_repos.py [--file repos.txt] [--output ./archive] [--dry-run]
"""

import argparse
import subprocess
import sys
from pathlib import Path


def parse_repo_file(filepath: Path) -> list[tuple[list[str], str]]:
    """
    Parse the repo list file and return a list of (path_parts, url) tuples.

    File format:
        Category            <- top-level, no indent
            Subcategory     <- 4-space indent
                https://... <- URL, any indent deeper than category
        # comment           <- ignored
        blank lines         <- ignored
    """
    entries: list[tuple[list[str], str]] = []
    category: str | None = None
    subcategory: str | None = None

    with open(filepath, encoding="utf-8") as f:
        for lineno, raw in enumerate(f, 1):
            line = raw.rstrip()

            # Skip blanks and comments
            if not line or line.lstrip().startswith("#"):
                continue

            stripped = line.lstrip()
            indent = len(line) - len(stripped)

            if stripped.startswith("https://") or stripped.startswith("http://"):
                # It's a URL — attach to current category stack
                if category is None:
                    print(f"Warning: URL on line {lineno} has no parent category, skipping.")
                    continue
                path_parts = [category]
                if subcategory:
                    path_parts.append(subcategory)
                entries.append((path_parts, stripped))

            elif indent == 0:
                # Top-level category
                category = stripped
                subcategory = None

            else:
                # Subcategory (any non-zero, non-URL indent)
                subcategory = stripped

    return entries


def repo_name_from_url(url: str) -> str:
    """Extract a filesystem-safe repo name from a GitHub URL."""
    name = url.rstrip("/").split("/")[-1]
    if name.endswith(".git"):
        name = name[:-4]
    return name


def clone_repo(url: str, dest: Path, dry_run: bool) -> bool:
    """
    Clone a repo to dest. If dest already exists and is a git repo, fetch instead.
    Returns True on success.
    """
    if dest.exists() and (dest / ".git").exists():
        print(f"  [FETCH]  {dest}")
        cmd = ["git", "-C", str(dest), "fetch", "--quiet", "--all"]
    else:
        print(f"  [CLONE]  {url}")
        print(f"        -> {dest}")
        cmd = ["git", "clone", "--depth=1", "--quiet", url, str(dest)]

    if dry_run:
        print(f"           (dry run, skipping)")
        return True

    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"  [ERROR]  {result.stderr.strip()}", file=sys.stderr)
        return False
    return True


def sanitize(name: str) -> str:
    """Make a string safe for use as a directory name."""
    # Replace slashes and other problematic chars
    for ch in r'/\:*?"<>|':
        name = name.replace(ch, "-")
    return name.strip()


def main():
    parser = argparse.ArgumentParser(
        description="Clone repos listed in a hierarchy file into an archive directory."
    )
    parser.add_argument(
        "--file", default="repos.txt",
        help="Path to the repo list file (default: repos.txt)"
    )
    parser.add_argument(
        "--output", default="./archive",
        help="Root output directory (default: ./archive)"
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Parse and print what would be cloned without actually cloning"
    )
    args = parser.parse_args()

    repo_file = Path(args.file)
    if not repo_file.exists():
        print(f"Error: repo file '{repo_file}' not found.", file=sys.stderr)
        sys.exit(1)

    output_root = Path(args.output)
    if not args.dry_run:
        output_root.mkdir(parents=True, exist_ok=True)

    entries = parse_repo_file(repo_file)
    if not entries:
        print("No repos found in file.")
        sys.exit(0)

    print(f"1trc repo archiver")
    print(f"  Source : {repo_file}")
    print(f"  Output : {output_root.resolve()}")
    print(f"  Repos  : {len(entries)}")
    if args.dry_run:
        print(f"  Mode   : DRY RUN")
    print()

    # Track duplicate URLs (same repo listed multiple times)
    seen_urls: set[str] = set()

    success = 0
    skipped = 0
    failed = 0
    current_section: list[str] = []

    for path_parts, url in entries:
        # Print section header when it changes
        if path_parts != current_section:
            print(f"\n{'  ' * (len(path_parts)-1)}{' / '.join(path_parts)}")
            current_section = path_parts

        if url in seen_urls:
            print(f"  [SKIP]   duplicate: {url}")
            skipped += 1
            continue
        seen_urls.add(url)

        # Build destination path
        safe_parts = [sanitize(p) for p in path_parts]
        repo_dir = output_root.joinpath(*safe_parts) / repo_name_from_url(url)

        ok = clone_repo(url, repo_dir, dry_run=args.dry_run)
        if ok:
            success += 1
        else:
            failed += 1

    print(f"\n{'─'*40}")
    print(f"Done.  Cloned: {success}  Skipped: {skipped}  Failed: {failed}")
    if failed:
        sys.exit(1)


if __name__ == "__main__":
    main()
