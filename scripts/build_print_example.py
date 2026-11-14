"""Regenerate the separate A4 HTML editions for the linear-equation lesson."""

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from leap.printing import build_documents


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    folder = ROOT / "print-examples" / "linear-equations"
    spec = json.loads((folder / "lesson.json").read_text(encoding="utf-8"))
    documents = build_documents(
        title=spec["title"], version=spec["version"], language=spec["language"],
        handout_html=(folder / "handout.fragment").read_text(encoding="utf-8"),
        questions=spec["questions"],
    )
    for edition, html in documents.items():
        path = folder / f"{edition}.html"
        if args.check:
            if not path.is_file() or path.read_text(encoding="utf-8") != html:
                print(f"Stale print edition: {path.name}", file=sys.stderr)
                return 1
        else:
            path.write_bytes(html.encode("utf-8"))
    print(f"{len(documents)} A4 HTML editions")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
