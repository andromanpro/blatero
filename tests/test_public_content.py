import pytest
import subprocess
import sys

from ci import check_public_content as gate
from ci import build_release


@pytest.mark.parametrize("name", [
    "DEVLOG.md", "CLAUDE.md", "docs/internal/report.md", ".release/release-signing-key.pem",
    "sessions/example/transcript.md", "config.json", "library.sqlite3",
    "Docs/Internal/report.md", "Поставки/report.md", ".RELEASE/release-signing-key.pem",
])
def test_internal_files_are_rejected(tmp_path, name):
    path = tmp_path / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("local data", encoding="utf-8")
    assert gate.check_inventory(tmp_path, [name])


def test_public_sources_and_documentation_are_accepted(tmp_path):
    for name in ["README.md", "CHANGELOG.md", "docs/development/README.md", "panel.py"]:
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("public source", encoding="utf-8")
    assert gate.check_inventory(tmp_path, ["README.md", "CHANGELOG.md", "docs/development/README.md", "panel.py"]) == []


def test_personal_home_path_is_reported_without_echoing_it(tmp_path):
    personal_path = "C:" + "/Users/" + "private-person/Documents/project"
    (tmp_path / "example.md").write_text(personal_path, encoding="utf-8")
    findings = gate.check_inventory(tmp_path, ["example.md"])
    assert len(findings) == 1
    assert "private-person" not in findings[0]


@pytest.mark.parametrize("name", ["example.md", "script.ps1", "Launcher.cs", "icon.svg"])
def test_secret_content_is_rejected(tmp_path, name):
    (tmp_path / name).write_text("credential = ghp_" + "A" * 40, encoding="utf-8")
    assert gate.check_inventory(tmp_path, [name])


def test_unreadable_file_is_a_failed_check(tmp_path):
    assert gate.check_inventory(tmp_path, ["missing.py"])


def test_source_package_contains_public_documentation_and_omits_internal_journal():
    assert build_release._runtime_file("CHANGELOG.md")
    assert build_release._runtime_file("docs/development/README.md")
    assert build_release._runtime_file("ci/check_public_content.py")
    assert build_release._runtime_file("ci/check_secrets.py")
    assert not build_release._runtime_file("DEVLOG.md")


def test_publication_command_fails_when_an_internal_file_is_staged(tmp_path):
    subprocess.run(["git", "init", "--quiet"], cwd=tmp_path, check=True)
    (tmp_path / "README.md").write_text("Public project", encoding="utf-8")
    subprocess.run(["git", "add", "--", "README.md"], cwd=tmp_path, check=True)
    command = [sys.executable, "-X", "utf8", str(gate.ROOT / "ci/check_public_content.py"),
               "--root", str(tmp_path)]
    before = subprocess.run(command, capture_output=True, text=True, encoding="utf-8")
    assert before.returncode == 0, before.stdout + before.stderr
    (tmp_path / "DEVLOG.md").write_text("Internal journal", encoding="utf-8")
    subprocess.run(["git", "add", "--", "DEVLOG.md"], cwd=tmp_path, check=True)
    after = subprocess.run(command, capture_output=True, text=True, encoding="utf-8")
    assert after.returncode == 1
    assert "DEVLOG.md" in after.stdout
