"""Embed the canonical v3 bridge in a self-contained teaching page.

The host still writes teaching content and registers the paired canonical note.
Reversible migration retains the original page in an inert backup comment.
"""
from __future__ import annotations
import argparse
import base64
from pathlib import Path
import re

REPO_ROOT = Path(__file__).resolve().parents[1]
BRIDGE_MARKER = "LEAP_HOST_BRIDGE"
KERNEL = REPO_ROOT / "examples/_shared/bridge-kernel.js"
REQUIRED_BRIDGE_PARTS = (("banner", BRIDGE_MARKER),("state object", "var bridge = {"),
    ("outbox queue", "outbox: []"),("hydrate()", "function hydrate("),
    ("drainOutbox()", "function drainOutbox("),("peekOutbox()", "function peekOutbox("),
    ("enqueue()", "function enqueue("),("renderBridge()", "renderBridge()"),
    ("per-item attempts", "bridge.attempts["),("assessment receipts", "applyToolResults"))


def bridge_status(path: Path) -> dict:
    text=path.read_text(encoding="utf-8")
    missing=[name for name, marker in REQUIRED_BRIDGE_PARTS if marker not in text]
    return {"present":not missing,"missing":missing,"has_banner":BRIDGE_MARKER in text}


def apply_bridge(path: Path, *, reverse: bool=False) -> str:
    raw=path.read_bytes(); text=raw.decode("utf-8").replace("\r\n","\n")
    newline="\r\n" if b"\r\n" in raw else "\n"
    backup=re.search(r"<!-- LEAP_ORIGINAL_V3:([A-Za-z0-9+/=]+) -->",text)
    if reverse:
        if not backup: return "no-bridge"
        path.write_bytes(base64.b64decode(backup.group(1)));return "reverted"
    if BRIDGE_MARKER in text: return "already"
    if "window.LEAP" in text:
        import importlib.util
        spec=importlib.util.spec_from_file_location("leap_bridge_normalizer",REPO_ROOT/"scripts/normalize_bridges.py")
        module=importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        normalize=module.normalize
        try: normalize(path)
        except (ValueError,AttributeError): raise SystemExit(f"Unsupported generated kernel: {path}")
        text=path.read_text(encoding="utf-8")
    else:
        if "var EVENT_COLOR = {" not in text or "getInteractionResult:" not in text:
            raise SystemExit(f"Missing LEAP anchors: {path}")
        # Migration of legacy fixture pages; override their public interface.
        # Generated production pages must provide their real configuration.
        insertion=KERNEL.read_text(encoding="utf-8")+'\nwindow.LEAP=createLeapBridge({example_id:"generated",subject:"math",node:{node_id:"generated.node",title:"Generated lesson",unit_tag:"generated"}});'
        text=re.sub(r'(var EVENT_COLOR = \{.*?\n  \};)',r'\1\n/* LEAP_HOST_BRIDGE legacy migration */',text,count=1,flags=re.S)
        text=text.replace("</script>","</script><script>\n"+insertion+"\n</script>",1)
    text+='\n<!-- LEAP_ORIGINAL_V3:'+base64.b64encode(raw).decode("ascii")+' -->\n'
    path.write_text(text,encoding="utf-8",newline=newline);return "patched"


def repair_bridge(path: Path) -> str:
    raw=path.read_bytes();text=raw.decode("utf-8").replace("\r\n","\n")
    if BRIDGE_MARKER not in text:return "unrepairable"
    if bridge_status(path)["present"]:return "ok"
    if "outbox: []" not in text and "    seq: 0, hooks:" in text:
        text=text.replace("    seq: 0, hooks:", "    outbox: [],\n    seq: 0, hooks:",1)
        path.write_text(text,encoding="utf-8",newline="\r\n" if b"\r\n" in raw else "\n")
        return "repaired" if bridge_status(path)["present"] else "unrepairable"
    return "unrepairable"


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument("paths",nargs="*")
    for arg in ("all","check","repair","revert"):parser.add_argument("--"+arg,action="store_true")
    args=parser.parse_args(argv); paths=sorted((REPO_ROOT/"examples").rglob("*.html")) if args.all or args.check or args.repair else [Path(p) for p in args.paths]
    if not paths:parser.error("provide paths or --all")
    failed=False
    for p in paths:
        if args.check:
            result=bridge_status(p);print(p.name,"COMPLETE" if result["present"] else result["missing"]);failed|=not result["present"]
        elif args.repair: print(p.name,repair_bridge(p))
        else:print(p.name,apply_bridge(p,reverse=args.revert))
    return 2 if failed else 0


if __name__=="__main__":raise SystemExit(main())
