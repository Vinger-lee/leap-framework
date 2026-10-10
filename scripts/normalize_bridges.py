"""Embed the shared bridge kernel; keep each page's subject controls intact."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
KERNEL = ROOT / "examples/_shared/bridge-kernel.js"


def normalize(path: Path) -> None:
    text=path.read_text(encoding="utf-8")
    match=re.search(r"window\.LEAP\s*=\s*\(function\s*\(\)\s*\{",text)
    if not match:
        if "createLeapBridge(" in text:
            start=text.index("/* LEAP_HOST_BRIDGE v3:")
            replacement=re.search(r"window\.LEAP\s*=\s*createLeapBridge",text[start:])
            if not replacement:raise ValueError(f"Missing bridge configuration: {path}")
            end=start+replacement.start()
            text=text[:start]+KERNEL.read_text(encoding="utf-8")+"\n"+text[end:]
            path.write_text(text,encoding="utf-8",newline="\n")
            return
        raise ValueError(f"Unsupported kernel: {path}")
    end=text.index("})();",match.start())+len("})();")
    current=text[match.start():end]
    example=re.search(r'example_id:\s*"([^"]+)"',current).group(1)
    subject=re.search(r'subject:\s*"([^"]+)"',current).group(1)
    node=re.search(r"node:\s*(\{[^}]+\})",current).group(1)
    config='{"example_id":'+json.dumps(example)+',"subject":'+json.dumps(subject)+',"node":'+node+'}'
    text=text[:match.start()]+KERNEL.read_text(encoding="utf-8")+'\nwindow.LEAP = createLeapBridge('+config+');'+text[end:]
    # Unobserved dimensions display an explicit unknown marker, not zero.
    text=text.replace("r.v.toFixed(2)", '(typeof r.v === "number" ? r.v.toFixed(2) : "未评估")')
    text=text.replace("(r.v * 100)", '((typeof r.v === "number" ? r.v : 0) * 100)')
    text=text.replace("a.overall_score.toFixed(2)", '(typeof a.overall_score === "number" ? a.overall_score.toFixed(2) : "未评估")')
    path.write_text(text,encoding="utf-8",newline="\n")


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument("paths",nargs="*");parser.add_argument("--all",action="store_true");args=parser.parse_args()
    paths=sorted((ROOT/"examples").rglob("*.html")) if args.all else [Path(p).resolve() for p in args.paths]
    for path in paths: normalize(path);print(path.relative_to(ROOT))


if __name__=="__main__":main()
