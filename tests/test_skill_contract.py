"""Validate the discoverable skill against real catalogs, without grading prose."""
import asyncio
import re
import tomllib

import pytest
import yaml

from leap import __version__
from leap.config import REPO_ROOT
from leap.server import build_server, registered_tool_names


SKILL = REPO_ROOT / ".agents/skills/leap-tutor/SKILL.md"

#: The explicit post-creation Domain Grounding skip-recording tool. Keep this in
#: sync with the runtime (src/leap/tools/session.py) and the skill documentation.
SKIP_TOOL = "set_domain_grounding_skip"


def skill_documents():
    assert SKILL.is_file()
    return [SKILL, *sorted((SKILL.parent / "references").glob("*.md"))]


def split_skill():
    source = SKILL.read_text(encoding="utf-8")
    assert source.startswith("---\n")
    frontmatter, body = source[4:].split("\n---\n", 1)
    return yaml.safe_load(frontmatter), body


def test_skill_frontmatter_tracks_the_repository_version():
    data, body = split_skill()
    assert data["name"] == SKILL.parent.name
    assert re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", data["name"])
    assert len(data["name"]) <= 64
    assert isinstance(data["description"], str) and data["description"].strip()
    assert len(data["description"]) <= 1024
    version = tomllib.loads(
        (REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    )["project"]["version"]
    assert data["metadata"]["leap-version"] == version == __version__
    assert data["metadata"]["status"] == "draft"
    # Main guidance should route to conditional details rather than inline manuals.
    assert len(body.splitlines()) <= 120


def test_skill_description_narrows_activation():
    data, _ = split_skill()
    description = data["description"].lower()
    # Explicit exclusions, in both languages, so ordinary chat and source work stay out.
    assert "do not trigger" in description
    assert "ordinary one-off explanations" in description
    assert "source code" in description
    assert "不触发" in data["description"]
    assert "普通" in data["description"]
    # Explicit inclusion examples must stay discoverable for real LEAP requests.
    assert "resuming an existing leap session" in description
    assert "按会话 id" in description


def test_skill_references_resolve_and_are_reachable():
    documents = skill_documents()
    reachable = {SKILL.resolve()}
    for document in documents:
        links = re.findall(r"\[[^\]]+\]\(([^)]+)\)", document.read_text(encoding="utf-8"))
        for target in links:
            assert not target.startswith(("http:", "https:")), "Keep operational references self-contained"
            path = (document.parent / target.split("#", 1)[0]).resolve()
            assert path.is_relative_to(SKILL.parent.resolve())
            assert path.is_file(), (document, target)
            reachable.add(path)
    assert {document.resolve() for document in documents} <= reachable


def test_skill_does_not_copy_the_runtime_policy():
    """The skill must cite get_teaching_delivery_policy instead of freezing its values."""
    for document in skill_documents():
        text = document.read_text(encoding="utf-8")
        assert not re.search(r"anatomy\.v\d", text), document
        assert "desktop_max_width" not in text
        assert "generation_requirements" not in text
        assert "get_teaching_delivery_policy" in text or document.name == "SKILL.md"


@pytest.mark.parametrize("profile", ["full", "quickstart"])
def test_skill_required_calls_exist_in_each_profile(profile):
    catalog = set(registered_tool_names(build_server(profile)))
    calls = set()
    for document in skill_documents():
        source = document.read_text(encoding="utf-8")
        for line in source.splitlines():
            names = set(re.findall(r"`([a-z][a-z0-9_]*)\(", line))
            if "full only" in line:
                assert names <= set(registered_tool_names(build_server("full")))
            else:
                calls.update(names)
    assert {"start_learning", "commit_assessment", "complete_session"} <= calls
    assert calls <= catalog, f"Unavailable {profile} calls: {calls - catalog}"


def test_quickstart_covers_the_documented_recovery_path():
    quickstart = set(registered_tool_names(build_server("quickstart")))
    full = set(registered_tool_names(build_server("full")))
    for required in (
        "commit_assessment",
        "resolve_misconception",
        "assess_misconception",
        "complete_session",
        SKIP_TOOL,
        "generate_final_report",
    ):
        assert required in quickstart, required
        assert required in full, required


def test_every_facade_next_call_target_is_available_in_quickstart():
    """A next_call the host cannot resolve means a broken chain in the narrow profile."""
    source = (REPO_ROOT / "src/leap/tools/facade.py").read_text(encoding="utf-8")
    targets = set(re.findall(r'"tool":\s*"([a-z_]+)"', source))
    assert targets
    quickstart = set(registered_tool_names(build_server("quickstart")))
    assert targets <= quickstart, sorted(targets - quickstart)


def test_obsidian_verifier_distinguishes_skill_files_from_knowledge_notes(tmp_path, monkeypatch):
    from scripts import verify_teaching_repository as verifier

    skill = tmp_path / ".agents/skills/tutor/SKILL.md"
    skill.parent.mkdir(parents=True)
    skill.write_text("---\nname: tutor\ndescription: A workflow\n---\n", encoding="utf-8")
    note = tmp_path / "docs/broken.md"
    note.parent.mkdir()
    note.write_text("A note missing required metadata", encoding="utf-8")
    monkeypatch.setattr(verifier.subprocess, "check_output", lambda *args, **kwargs: b".agents/skills/tutor/SKILL.md\0docs/broken.md\0")

    report = verifier.verify(tmp_path)

    assert report["markdown_notes"] == 1
    assert report["errors"] and all(error.startswith("docs/broken:") for error in report["errors"])


DOCS_TO_CHECK = [
    SKILL,
    *sorted((SKILL.parent / "references").glob("*.md")),
    REPO_ROOT / "docs/agent-skill.md",
    REPO_ROOT / "docs/host-config.md",
]


def test_documented_tool_calls_match_the_catalog():
    """Every documented `tool(arg, ...)` must name a real tool and real parameters."""
    full_server = build_server("full")
    full_tools = asyncio.run(full_server.list_tools())
    schemas = {tool.name: tool.model_dump(by_alias=True)["inputSchema"] for tool in full_tools}
    call = re.compile(r"`([a-z][a-z0-9_]*)\s*\(([^`]*)\)`")
    problems = []
    for document in DOCS_TO_CHECK:
        for lineno, line in enumerate(document.read_text(encoding="utf-8").splitlines(), 1):
            for name, arguments in call.findall(line):
                if name not in schemas:
                    problems.append((document.name, lineno, name))
                    continue
                properties = schemas[name].get("properties", {})
                for raw in arguments.split(","):
                    match = re.match(r"([a-z_][a-z0-9_]*)", raw.strip())
                    if match and match.group(1) not in properties:
                        problems.append((document.name, lineno, f"{name}.{match.group(1)}"))
    assert not problems, problems


def test_skill_routes_requested_printing_to_the_runtime():
    _, body = split_skill()
    assert "references/printing.md" in body
    source = (SKILL.parent / "references/printing.md").read_text(encoding="utf-8")
    for tool in ("get_print_materials", "save_print_materials", "export_print_pdf"):
        assert f"`{tool}(" in source
