import json
from pathlib import Path
import sys
from types import SimpleNamespace
from unittest.mock import MagicMock, patch
import urllib.error

import pytest

import call_watch as watch


SETTINGS = {"call_auto_telemost": True, "call_auto_talk": True, "call_auto_record_acknowledged": True}
USE = {"app": "telemost", "path": r"c:\apps\telemost.exe", "start": 12345}


def test_explicit_app_and_recording_opt_in_are_required():
    assert watch.enabled(SETTINGS)
    assert not watch.enabled({**SETTINGS, "call_auto_record_acknowledged": False})
    assert not watch.enabled({"call_auto_record_acknowledged": True})


def test_debounce_mute_and_manual_stop_do_not_duplicate_a_recording():
    episodes = watch.Episodes()
    assert episodes.observe([USE], SETTINGS, 1000) == []
    first = episodes.observe([USE], SETTINGS, 1003)
    assert len(first) == 1
    episodes.rows["telemost"]["handled"] = True
    assert episodes.observe([], SETTINGS, 1010) == []
    assert episodes.observe([{**USE, "start": 55555}], SETTINGS, 1020) == []
    replay = watch.Episodes(json.loads(json.dumps(episodes.rows)))
    assert replay.observe([USE], SETTINGS, 1023) == []
    assert replay.observe([{**USE, "start": 77777}], SETTINGS, 1200) == []
    assert len(replay.observe([{**USE, "start": 77777}], SETTINGS, 1203)) == 1


def test_unselected_application_is_ignored():
    episodes = watch.Episodes()
    settings = {**SETTINGS, "call_auto_telemost": False}
    assert episodes.observe([USE], settings, 1000) == []
    assert episodes.observe([USE], settings, 1003) == []


def fake_registry(records):
    key = MagicMock()
    key.__enter__.return_value = key
    child = MagicMock()
    child.__enter__.return_value = child
    registry = SimpleNamespace(HKEY_CURRENT_USER=1)
    registry.OpenKey = lambda parent, name: key if name == watch.MIC_KEY else records[name]
    registry.QueryInfoKey = lambda _key: (len(records), 0, 0)
    registry.EnumKey = lambda _key, index: list(records)[index]
    registry.QueryValueEx = lambda child, name: (child.values[name], 0)
    for data in records.values():
        data.__enter__.return_value = data
    return registry


def test_microphone_detection_excludes_idle_stale_dead_and_other_apps(monkeypatch):
    records = {}
    for filename, start, stop in [("telemost.exe", 200, 0), ("ktalk.exe", 200, 250), ("browser.exe", 200, 0), ("yandextelemost.exe", 50, 0), ("konturtalk.exe", 200, 0)]:
        key = MagicMock()
        key.values = {"LastUsedTimeStart": start, "LastUsedTimeStop": stop}
        records["c:#apps#" + filename] = key
    monkeypatch.setitem(sys.modules, "winreg", fake_registry(records))
    monkeypatch.setattr(watch.sys, "platform", "win32")
    processes = {"c:\\apps\\" + name: [100] for name in ("telemost.exe", "ktalk.exe", "browser.exe", "yandextelemost.exe")}
    with patch.object(watch, "active_processes", return_value=processes):
        uses = watch.microphone_uses()
    assert [row["app"] for row in uses] == ["telemost"]


def test_login_registration_is_quoted_and_disabled_setting_removes_it(tmp_path, monkeypatch):
    import config
    registry = MagicMock()
    monkeypatch.setitem(sys.modules, "winreg", registry)
    monkeypatch.setattr(watch.sys, "platform", "win32")
    monkeypatch.setattr(watch.sys, "executable", str(tmp_path / "Python runtime" / "python.exe"))
    with patch.object(config, "load", return_value=SETTINGS), patch.object(watch, "lock_is_held", return_value=True):
        watch.synchronize(Path("F:/App with spaces"), tmp_path, "x" * 40)
    command = registry.SetValueEx.call_args.args[-1]
    assert '"F:\\App with spaces\\call_watch.py"' in command or '"F:/App with spaces\\call_watch.py"' in command
    assert "x" * 40 not in command
    assert (tmp_path / ".call-watch-token").read_text() == "x" * 40
    registry.QueryValueEx.return_value = (command, 1)
    with patch.object(config, "load", return_value={}):
        watch.synchronize(tmp_path, tmp_path, "x" * 40)
    registry.DeleteValue.assert_called_once()


def test_native_process_metadata_probe_does_not_inspect_windows():
    if sys.platform != "win32":
        pytest.skip("Windows API")
    assert isinstance(watch.active_processes(), dict)


def test_telemost_qt_helper_is_recognized_only_in_its_own_installation():
    assert watch.application(r"C:\Program Files\Yandex\YandexTelemost\QtWebEngineProcess.exe") == "telemost"
    assert watch.application(r"C:\Other App\QtWebEngineProcess.exe") is None


def test_closed_panel_is_launched_once_and_request_uses_local_auth(tmp_path):
    token = tmp_path / "token"
    token.write_text("x" * 40)
    response = MagicMock()
    response.__enter__.return_value.read.return_value = b'{"state":"started"}'
    opener = MagicMock()
    opener.open.side_effect = [urllib.error.URLError("closed"), response]
    with patch.object(watch.urllib.request, "build_opener", return_value=opener), patch.object(watch.subprocess, "Popen") as launch, patch.object(watch.os, "startfile", create=True) as browser, patch.object(watch.time, "sleep"):
        result = watch.start_capture(tmp_path, tmp_path, token, 8877, {**USE, "event": "a" * 64})
    assert result["state"] == "started"
    launch.assert_called_once()
    assert launch.call_args.args[0][1] == str(tmp_path / "panel.py")
    assert opener.open.call_args.args[0].get_header("Authorization") == "Bearer " + "x" * 40
    assert opener.open.call_args.args[0].full_url == "http://localhost:8877/api/call-watch/start"
    browser.assert_called_once()


@pytest.mark.parametrize("value", [[], {"ts": "bad"}, None])
def test_corrupt_watcher_status_does_not_break_panel_init(tmp_path, value):
    (tmp_path / "call-watch-state.json").write_text(json.dumps(value))
    assert watch.status(tmp_path)["running"] is False
