from pathlib import Path

import pytest

import project_session_catalog as catalog


@pytest.mark.parametrize("text", [
    "D:/Projects/Example/file.py", r"D:\Projects\Example\file.py", r"D\:\Projects\Example\file.py",
])
def test_project_paths_use_the_selected_workspace(monkeypatch, text):
    monkeypatch.setattr(catalog, "WORKSPACE_ROOT", Path("D:/Projects"))
    record = catalog.new_record("codex", "test", "source")
    catalog.add_message(record, "user", text, "source:1")
    assert record["paths"] == {"Example"}


def test_unrelated_workspace_path_is_not_assigned(monkeypatch):
    monkeypatch.setattr(catalog, "WORKSPACE_ROOT", Path("D:/Projects"))
    record = catalog.new_record("codex", "test", "source")
    catalog.add_message(record, "user", "E:/Other/Example/file.py", "source:1")
    assert record["paths"] == set()


def test_project_catalog_scans_the_selected_root(tmp_path, monkeypatch):
    workspace = tmp_path / "workspace"
    project = workspace / "Example"
    project.mkdir(parents=True)
    (project / "README.md").write_text("# Example\nProject description", encoding="utf-8")
    (workspace / ".cache").mkdir()
    output = tmp_path / "output"
    output.mkdir()
    monkeypatch.setattr(catalog, "WORKSPACE_ROOT", workspace)
    result = catalog.project_catalog(output)
    assert [entry["name"] for entry in result] == ["Example"]
    assert result[0]["workspace"] == str(project)
