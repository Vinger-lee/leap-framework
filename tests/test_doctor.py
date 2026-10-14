"""Installation self-check (``python -m leap.doctor``).

The doctor exists so an installation problem surfaces as a named, actionable
row instead of an opaque tool error later. It must also stay read-only: no check
may create, migrate or write the configured database.
"""

from __future__ import annotations

from pathlib import Path

import leap.doctor as doctor


def test_run_checks_reports_a_working_installation():
    report = doctor.run_checks()

    assert report["ok"] is True, report["failed"]
    assert {check["name"] for check in report["checks"]} == {
        name for name, _ in doctor.CHECKS
    }
    assert all(check["status"] in {"ok", "warn", "fail"} for check in report["checks"])
    dependencies = next(c for c in report["checks"] if c["name"] == "dependencies")
    assert dependencies["status"] == "ok"
    profiles = next(c for c in report["checks"] if c["name"] == "tool_profiles")
    assert "full:" in profiles["detail"] and "quickstart:" in profiles["detail"]


def test_render_is_readable_and_mentions_every_check():
    text = doctor.render(doctor.run_checks())

    assert "LEAP doctor" in text
    for name, _ in doctor.CHECKS:
        assert name in text
    assert "all required checks passed" in text


def test_json_report_is_machine_readable(capsys):
    exit_code = doctor.main(["--json"])
    payload = capsys.readouterr().out

    assert exit_code == 0
    import json

    report = json.loads(payload)
    assert report["ok"] is True
    assert isinstance(report["checks"], list)


def test_unknown_profile_is_reported_to_the_operator(capsys):
    exit_code = doctor.main(["--profile", "nope"])
    captured = capsys.readouterr()

    assert exit_code == 1
    assert "unknown tool profile" in captured.err


def test_database_check_never_creates_the_configured_database(tmp_path, monkeypatch):
    target = tmp_path / "data" / "leap.db"
    target.parent.mkdir()
    monkeypatch.setattr(
        doctor,
        "load_config",
        lambda: {"database_path": str(target), "artifact_root": str(tmp_path / "artifacts")},
    )

    status, detail = doctor._database()

    assert status == "ok"
    assert str(target) in detail
    assert not target.exists()


def test_database_check_reports_a_missing_directory_as_a_warning(tmp_path, monkeypatch):
    target = tmp_path / "not-there-yet" / "leap.db"
    monkeypatch.setattr(
        doctor,
        "load_config",
        lambda: {"database_path": str(target), "artifact_root": str(tmp_path / "artifacts")},
    )

    status, _ = doctor._database()

    assert status == "warn"


def test_schema_check_uses_a_throwaway_database():
    detail = dict((check["name"], check["detail"]) for check in doctor.run_checks()["checks"])
    status = dict((check["name"], check["status"]) for check in doctor.run_checks()["checks"])

    assert status["schema"] == "ok"
    assert "empty database" in detail["schema"]
    # The repository's own data directory must be untouched by a self-check.
    assert not (Path(doctor.REPO_ROOT) / "data" / "doctor.db").exists()
