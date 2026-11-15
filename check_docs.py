"""Fail if a relative Markdown link points to a file that does not exist."""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
LINK = re.compile(r"\[[^\]]*\]\(([^)\s]+)\)")
SKIP_DIRS = {".git", ".venv", "node_modules", "mlruns"}


def broken_links(root: Path = ROOT) -> list[str]:
    problems = []
    for md in sorted(root.rglob("*.md")):
        if SKIP_DIRS & set(md.relative_to(root).parts):
            continue
        for target in LINK.findall(md.read_text(encoding="utf-8")):
            if target.startswith(("http://", "https://", "mailto:", "#")):
                continue
            path = target.split("#", 1)[0]
            if path and not (md.parent / path).exists():
                problems.append(f"{md.relative_to(root)}: broken link -> {target}")
    return problems


def main() -> int:
    problems = broken_links()
    for line in problems:
        print(line, file=sys.stderr)
    print(f"{len(problems)} broken link(s)")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
