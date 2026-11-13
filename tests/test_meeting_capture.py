import asyncio
import json
import uuid
from unittest.mock import patch

import pytest

import meeting_capture as capture
import panel
from project_store import Store
import session_schema


@pytest.fixture
def example(tmp_path):
    store = Store(tmp_path / ".projects")
    folder = tmp_path / "Материалы"
    folder.mkdir()
    (folder / "Реестр задач.md").write_text("TASK-42 Проверить печать этикеток 203 DPI", encoding="utf-8")
    project = store.create_project("Этикетки", str(folder))
    who, _ = store.local_agent()
    task = store.create_task({"project_id": project["id"], "title": "TASK-42 Печать", "goal": "Проверить PDF"}, who)["task"]
    sdir = tmp_path / "sessions" / "recording"
    sdir.mkdir(parents=True)
    session_schema.initialize(sdir, {"name": "Разговор", "date": "2026-11-13", "time": "18:00", "type": "встреча", "contour": "work"})
    (sdir / "audio-me.wav").write_bytes(b"UNCHANGED-RAW-PCM")
    (sdir / "transcript.md").write_text("[Я] Обсуждаем печать этикеток на принтере 203 DPI. Нужно проверить PDF и размер этикетки.\n" * 6, encoding="utf-8")
    return store, sdir, project, task


def test_context_is_added_to_live_session_and_next_prompt(example, tmp_path):
    store, sdir, project, task = example
    before = {p.name: p.read_bytes() for p in sdir.iterdir() if p.suffix in {".wav", ".md"}}
    with patch("llm.chat", side_effect=AssertionError("local context must stay local")):
        prepared = capture.prepare(store, tmp_path, sdir, {"name": "Проверка печати", "project_id": project["id"], "task_id": task["id"]})
        capture.apply(store, tmp_path, sdir, prepared, origin="manual")
    assert "203 DPI" in panel.copilot.meeting_context(sdir)
    assert json.loads((sdir / "meta.json").read_text(encoding="utf-8"))["task_ids"] == [task["id"]]
    assert all((sdir / name).read_bytes() == content for name, content in before.items())
    with store.connect() as conn:
        assert conn.execute("SELECT count(*) FROM material_links WHERE work_item_id=?", (task["id"],)).fetchone()[0] == 1


def test_partial_context_publication_never_enters_hint_context(example, tmp_path):
    store, sdir, project, task = example
    prepared = capture.prepare(store, tmp_path, sdir, {"project_id": project["id"], "task_id": task["id"]})
    with patch.object(capture.session_schema, "write_meta", side_effect=OSError("disk failure")), pytest.raises(OSError):
        capture.apply(store, tmp_path, sdir, prepared, origin="manual")
    assert "203 DPI" not in panel.copilot.meeting_context(sdir)
    capture.apply(store, tmp_path, sdir, prepared, origin="manual")
    assert "203 DPI" in panel.copilot.meeting_context(sdir)


def test_new_context_supplies_only_its_own_dossier_to_hints(example, tmp_path):
    store, sdir, project, task = example
    (sdir / "dossier.md").write_text("OLD-PROJECT-CONTEXT", encoding="utf-8")
    prepared = capture.prepare(store, tmp_path, sdir, {"project_id": project["id"], "task_id": task["id"]})
    capture.apply(store, tmp_path, sdir, prepared, origin="manual")
    prompt = panel.copilot.meeting_context(sdir)
    assert "203 DPI" in prompt
    assert "OLD-PROJECT-CONTEXT" not in prompt


def test_correcting_context_replaces_only_its_task_links(example, tmp_path):
    store, sdir, project, task = example
    prepared = capture.prepare(store, tmp_path, sdir, {"project_id": project["id"], "task_id": task["id"]})
    capture.apply(store, tmp_path, sdir, prepared, origin="manual")
    other = store.create_task({"project_id": project["id"], "title": "Другая задача"}, store.local_agent()[0])["task"]
    prepared = capture.prepare(store, tmp_path, sdir, {"project_id": project["id"], "task_id": other["id"]})
    capture.apply(store, tmp_path, sdir, prepared, origin="manual")
    with store.connect() as conn:
        assert [row[0] for row in conn.execute("SELECT work_item_id FROM material_links")] == [other["id"]]
    capture.apply(store, tmp_path, sdir, prepared, origin="manual")
    with store.connect() as conn:
        assert conn.execute("SELECT count(*) FROM material_links WHERE work_item_id=?", (other["id"],)).fetchone()[0] == 1


def topic(sdir, project_id=None, **changes):
    return {"ready": True, "title": "Проверка печати этикеток", "goal": "Проверить PDF и размер этикетки", "evidence": capture.transcript(sdir).splitlines()[0], "project_id": project_id, "task_id": None, **changes}


def test_recognize_and_create_card_are_grounded_and_idempotent(example):
    store, sdir, project, _ = example
    with patch("llm.chat", return_value=json.dumps(topic(sdir, project["id"]))):
        recognized = capture.recognize(store, sdir)
    identity = capture.task_from_topic(store, sdir, recognized)
    assert capture.task_from_topic(store, sdir, recognized) == identity
    assert len(store.tasks()) == 2
    assert store.task(identity)["status"] == "inbox"
    assert store.detail(identity)["sources"][0]["label"] == recognized["evidence"]


@pytest.mark.parametrize("changes", [{"evidence": "not in transcript" * 8}, {"project_id": str(uuid.uuid4())}, {"task_id": str(uuid.uuid4())}, {"title": ""}])
def test_invalid_model_topic_cannot_create_a_card(example, changes):
    store, sdir, _, _ = example
    with patch("llm.chat", return_value=json.dumps(topic(sdir, **changes))), pytest.raises(ValueError):
        capture.recognize(store, sdir)
    assert len(store.tasks()) == 1


def test_short_transcript_never_calls_model(example):
    store, sdir, _, _ = example
    (sdir / "transcript.md").write_text("Добрый день", encoding="utf-8")
    with patch("llm.chat", side_effect=AssertionError("no model")), pytest.raises(ValueError, match="мало"):
        capture.recognize(store, sdir)


def test_truncated_topic_cannot_create_a_card(example):
    store, sdir, _, _ = example
    with patch("llm.chat", return_value=json.dumps(topic(sdir))[:-5]), pytest.raises(ValueError):
        capture.recognize(store, sdir)
    assert len(store.tasks()) == 1


def test_prepared_meeting_can_supply_context_without_moving_pcm(example, tmp_path):
    store, sdir, project, task = example
    source = tmp_path / "sessions" / "prepared"
    source.mkdir()
    session_schema.initialize(source, {"name": "Готовая повестка", "type": "встреча", "contour": "work", "project_id": project["id"], "task_ids": [task["id"]]})
    (source / "brief.md").write_text("Обсудить результат испытания", encoding="utf-8")
    original = {p: p.read_bytes() for p in source.iterdir()}
    prepared = capture.prepare(store, tmp_path, sdir, {"source_session": source.name})
    capture.apply(store, tmp_path, sdir, prepared, origin="manual")
    assert "Обсудить результат испытания" in panel.copilot.meeting_context(sdir)
    assert all(p.read_bytes() == content for p, content in original.items())
    assert (sdir / "audio-me.wav").read_bytes() == b"UNCHANGED-RAW-PCM"


def test_changed_session_cannot_receive_background_context(example, tmp_path, monkeypatch):
    store, sdir, project, task = example
    monkeypatch.setattr(panel, "BASE", tmp_path)
    monkeypatch.setitem(panel.state, "sdir", sdir)
    monkeypatch.setitem(panel.state, "generation", 42)
    job = panel.capture_session_job()
    original = capture.prepare
    def switch_during_prepare(*args):
        value = original(*args)
        panel.state["generation"] += 1
        return value
    with patch.object(capture, "prepare", side_effect=switch_during_prepare):
        asyncio.run(panel.do_capture_context(job, {"project_id": project["id"], "task_id": task["id"]}))
    assert not (sdir / capture.DOSSIER_FILE).exists()
    assert (sdir / "audio-me.wav").read_bytes() == b"UNCHANGED-RAW-PCM"


def test_automatic_topic_creates_task_and_connects_it_to_the_same_recording(example, tmp_path, monkeypatch):
    store, sdir, project, _ = example
    monkeypatch.setattr(panel, "BASE", tmp_path)
    monkeypatch.setitem(panel.state, "sdir", sdir)
    monkeypatch.setitem(panel.state, "generation", 42)
    job = panel.capture_session_job()
    messages = []
    async def broadcast(message):
        messages.append(message)
    with patch("llm.chat", return_value=json.dumps(topic(sdir, project["id"]))), patch.object(panel, "broadcast", broadcast), patch.object(panel, "init_payload", return_value={"type": "init"}):
        asyncio.run(panel.do_capture_context(job, {"recognize": True}, automatic=True))
    meta = json.loads((sdir / "meta.json").read_text(encoding="utf-8"))
    assert meta["capture_context_origin"] == "conversation"
    assert store.task(meta["task_ids"][0])["status"] == "inbox"
    assert len(store.tasks()) == 2
    assert messages[0]["ok"] is True
    assert "203 DPI" in panel.copilot.meeting_context(sdir)
    assert (sdir / "audio-me.wav").read_bytes() == b"UNCHANGED-RAW-PCM"


def test_automatic_topic_waits_for_cloud_setting(example, monkeypatch):
    _, sdir, _, _ = example
    monkeypatch.setitem(panel.state, "sdir", sdir)
    monkeypatch.setitem(panel.state, "capture_context_job", None)
    meta = json.loads((sdir / "meta.json").read_text(encoding="utf-8"))
    session_schema.write_meta(sdir, {**meta, "capture_auto_context": True})
    with patch.object(panel, "recording_active", return_value=True), patch.object(panel.cfg, "load", return_value={"cloud_processing_acknowledged": False}), patch.object(panel, "spawn_session_background") as spawn:
        panel.maybe_capture_context(1000)
    spawn.assert_not_called()


def test_unplanned_start_uses_normal_capture_and_a_new_session(example, tmp_path, monkeypatch):
    _, sdir, _, _ = example
    monkeypatch.setattr(panel, "BASE", tmp_path)
    monkeypatch.setitem(panel.state, "sdir", sdir)
    monkeypatch.setitem(panel.state, "generation", 7)
    monkeypatch.setitem(panel.state, "rec_transition_busy", False)
    monkeypatch.setitem(panel.state, "speech_switch_busy", False)
    started = []
    async def broadcast(_message):
        pass
    message = {"action": "start", "mtype": "встреча", "unplanned": True, "request_id": "a" * 32,
        "recording_acknowledged": True, "session": sdir.name, "generation": 7, "server_epoch": panel.WS_SCOPE_EPOCH}
    with patch.object(panel, "recording_active", return_value=False), patch.object(panel.video_manager, "is_active", return_value=False), patch.object(panel, "rec_start", side_effect=lambda: started.append(panel.state["sdir"])), patch.object(panel, "broadcast", broadcast), patch.object(panel, "init_payload", return_value={}), patch.object(panel, "pending_emulation_question", return_value=None):
        asyncio.run(panel.handle_ws_recording(None, message))
    assert len(started) == 1 and started[0] != sdir
    meta = json.loads((started[0] / "meta.json").read_text(encoding="utf-8"))
    assert meta["capture_auto_context"] and meta["contour"] == "work"
    assert not meta.get("workspace_path")
    assert (sdir / "audio-me.wav").read_bytes() == b"UNCHANGED-RAW-PCM"


@pytest.mark.parametrize("app", ["telemost", "talk"])
def test_call_event_api_starts_exactly_once_and_requires_current_app_use(example, tmp_path, monkeypatch, app):
    from fastapi.testclient import TestClient
    _, sdir, _, _ = example
    monkeypatch.setattr(panel, "BASE", tmp_path)
    values = {"sdir": sdir, "generation": 1, "rec_proc": None, "rec_sdir": None,
              "rec_transition_busy": False, "speech_switch_busy": False, "require_auth": False}
    for key, value in values.items():
        monkeypatch.setitem(panel.state, key, value)
    executable = {"telemost": "telemost.exe", "talk": "ktalk.exe"}[app]
    use = {"app": app, "path": "c:\\apps\\" + executable, "start": 1234}
    calls = []
    class Process:
        def poll(self):
            return None
    def start():
        calls.append(panel.state["sdir"])
        panel.state.update(rec_proc=Process(), rec_sdir=panel.state["sdir"])
    async def broadcast(_message):
        pass
    client = TestClient(panel.app, base_url="http://localhost", client=("127.0.0.1", 45678))
    headers = {"Origin": "http://localhost"}
    settings = {"call_auto_" + app: True, "call_auto_record_acknowledged": True}
    with patch.object(panel.cfg, "load", return_value={**panel.cfg.DEFAULTS, **settings}), patch.object(panel.call_watch, "microphone_uses", return_value=[use]) as microphone, patch.object(panel, "rec_start", side_effect=start), patch.object(panel, "init_payload", return_value={}), patch.object(panel, "broadcast", broadcast), patch.object(panel.video_manager, "is_active", return_value=False), patch.object(panel, "pending_emulation_question", return_value=None):
        response = client.post("/api/call-watch/start", json={**use, "event": "a" * 64}, headers=headers)
        assert response.status_code == 200, response.text
        assert response.json()["state"] == "started"
        again = client.post("/api/call-watch/start", json={**use, "event": "a" * 64}, headers=headers)
        assert again.json()["replayed"]
        ended = client.post("/api/call-watch/start", json={**use, "start": 2345, "event": "b" * 64}, headers=headers)
        assert ended.json()["state"] == "ended"
        # Some clients release device access during in-app mute. Returning after
        # ten minutes must keep the same capture even if the watcher sees a new episode.
        session = panel.state["sdir"]
        process = panel.state["rec_proc"]
        pcm = session / "audio-me.wav"
        pcm.write_bytes(b"PCM-CONTINUES-THROUGH-APP-MUTE")
        episodes = panel.call_watch.Episodes()
        episodes.observe([use], settings, 1000)
        episodes.observe([use], settings, 1003)
        episodes.rows[app]["handled"] = True
        episodes.observe([], settings, 1100)
        resumed_use = {**use, "start": 3456}
        episodes.observe([resumed_use], settings, 1700)
        resumed = episodes.observe([resumed_use], settings, 1703)
        assert len(resumed) == 1
        microphone.return_value = [resumed_use]
        unmuted = client.post("/api/call-watch/start", json=resumed[0], headers=headers)
        assert unmuted.json()["state"] == "busy"
        assert panel.state["sdir"] == session
        assert panel.state["rec_proc"] is process and panel.recording_active(session)
        assert pcm.read_bytes() == b"PCM-CONTINUES-THROUGH-APP-MUTE"
    assert len(calls) == 1
