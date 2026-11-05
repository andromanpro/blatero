"""WGC → bounded latest frame → local Matroska. No microphone, STT or cloud access."""

from __future__ import annotations

from fractions import Fraction
import hashlib
import json
import os
from pathlib import Path
import queue
import shutil
import sys
import threading
import time

import video_capture
import video_sources

MAX_SECONDS = 4 * 60 * 60
MIN_FREE = 100 * 1024 * 1024


def encode_frame(array, width, height):
    import av
    import numpy as np

    scale = min(width / array.shape[1], height / array.shape[0])
    fitted_w = max(2, int(array.shape[1] * scale) // 2 * 2)
    fitted_h = max(2, int(array.shape[0] * scale) // 2 * 2)
    image = av.VideoFrame.from_ndarray(array, format="bgra").reformat(fitted_w, fitted_h, "rgb24")
    canvas = np.zeros((height, width, 3), dtype=np.uint8)
    x, y = (width - fitted_w) // 2, (height - fitted_h) // 2
    canvas[y : y + fitted_h, x : x + fitted_w] = image.to_ndarray(format="rgb24")
    return av.VideoFrame.from_ndarray(canvas, format="rgb24")


def verify(path: Path) -> dict:
    import av

    with av.open(str(path)) as saved:
        video = saved.streams.video
        if len(video) != 1 or saved.streams.audio:
            raise ValueError("video_invalid_container")
        first = next(saved.decode(video=0), None)
        if first is None:
            raise ValueError("video_empty")
        width, height = first.width, first.height
    with path.open("rb") as original:
        digest = hashlib.file_digest(original, "sha256").hexdigest()
    return {"width": width, "height": height, "sha256": digest, "bytes": path.stat().st_size}


def record(config: dict, commands: queue.Queue, start_listener=None) -> None:
    folder = Path(config["folder"])
    state = video_capture.read_state(folder)
    state["worker_pid"] = os.getpid()
    state["heartbeat"] = time.time()
    video_capture.atomic_state(folder, state)
    capture = control = container = output = None
    stop_reason = ""
    frame_lock = threading.Lock()
    latest = None
    closed = threading.Event()
    latest_ts = last_copy = 0.0
    started = None
    preview_saved = False
    frames = 0
    last_pts = -1
    try:
        import av
        from windows_capture import WindowsCapture

        # Avoid the observed NumPy DLL startup stall with an already blocking stdin reader.
        # Native smoke covers initialization before opening the control-reader thread.
        if start_listener is not None:
            threading.Thread(target=start_listener, daemon=True).start()
        source = video_sources.validate(config["source"])
        kwargs = (
            {"window_hwnd": source["hwnd"]}
            if source["kind"] == "window"
            else {"monitor_index": source["index"]}
        )
        capture = WindowsCapture(cursor_capture=True, **kwargs)
        fps = config["fps"]

        @capture.event
        def on_frame_arrived(frame, _control):
            nonlocal latest, latest_ts, last_copy
            now = time.monotonic()
            if now - last_copy < 1 / fps:
                return
            # Bound native/copy memory; never build an unbounded frame queue.
            if frame.width * frame.height > 36_000_000:
                commands.put({"action": "frame_too_large"})
                _control.stop()
                return
            with frame_lock:
                latest = frame.frame_buffer.copy()
                latest_ts = frame.timespan
                last_copy = now

        @capture.event
        def on_closed():
            closed.set()

        capture.frame_handler = on_frame_arrived
        capture.closed_handler = on_closed
        control = capture.start_free_threaded()
        video_sources.validate(source)
        ready_deadline = time.monotonic() + 10
        prepared_at = time.monotonic()
        last_state = 0
        width = height = 0
        while True:
            now = time.monotonic()
            if closed.is_set():
                raise ValueError("video_source_closed")
            if now - last_state >= 0.5:
                video_sources.validate(source)
                if shutil.disk_usage(folder).free < MIN_FREE:
                    raise ValueError("video_disk_low")
                state.update(
                    heartbeat=time.time(),
                    frames=frames,
                    seconds=round(now - started, 2) if started is not None else 0,
                )
                video_capture.atomic_state(folder, state)
                last_state = now
            with frame_lock:
                array = latest
                stamp = latest_ts
            if array is not None and not preview_saved:
                from PIL import Image

                preview = Image.fromarray(array[:, :, [2, 1, 0]])
                preview.thumbnail((1280, 720))
                with (folder / "preview.png").open("xb") as png:
                    preview.save(png, format="PNG")
                preview_saved = True
                state.update(phase="preview", first_frame_qpc=stamp)
                video_capture.atomic_state(folder, state)
            if not preview_saved and now > ready_deadline:
                raise ValueError("video_no_frames")
            if started is None and now - prepared_at > 90:
                stop_reason = "video_preview_expired"
                break
            try:
                command = commands.get(timeout=0.015)
            except queue.Empty:
                command = {}
            action = command.get("action")
            if action in {"stop", "cancel", "abort", "parent_closed", "frame_too_large"}:
                stop_reason = action
                break
            if action == "start" and started is None:
                if not preview_saved:
                    raise ValueError("video_preview_required")
                # Keep the same WGC capture item between preview and recording.
                scale = min(1, 1920 / array.shape[1], 1080 / array.shape[0])
                width = max(2, int(array.shape[1] * scale) // 2 * 2)
                height = max(2, int(array.shape[0] * scale) // 2 * 2)
                output = (folder / "recording.partial.mkv").open("xb")
                state["file"] = "recording.partial.mkv"
                container = av.open(
                    output,
                    mode="w",
                    format="matroska",
                    options={"cluster_time_limit": "1000", "flush_packets": "1"},
                )
                stream = container.add_stream("libx264", rate=fps)
                stream.width, stream.height, stream.pix_fmt = width, height, "yuv420p"
                stream.options = {"preset": "ultrafast", "tune": "zerolatency", "crf": "23"}
                stream.codec_context.time_base = Fraction(1, fps)
                stream.codec_context.gop_size = fps
                stream.codec_context.thread_count = 2
                started = now
                state.update(
                    phase="recording",
                    started_at=time.time(),
                    monotonic_start=now,
                    width=width,
                    height=height,
                    file="recording.partial.mkv",
                )
                video_capture.atomic_state(folder, state)
            if started is not None:
                if now - started > MAX_SECONDS:
                    raise ValueError("video_duration_limit")
                target = int((now - started) * fps)
                # If encoding is slow, represent elapsed time with PTS, not a growing backlog.
                if target > last_pts:
                    frame = encode_frame(array, width, height)
                    frame.pts, frame.time_base = target, Fraction(1, fps)
                    for packet in stream.encode(frame):
                        container.mux(packet)
                    frames += 1
                    last_pts = target
                    state.update(source_width=array.shape[1], source_height=array.shape[0])
            time.sleep(0.005)
        if started is not None:
            state["phase"] = "stopping"
            video_capture.atomic_state(folder, state)
            for packet in stream.encode():
                container.mux(packet)
            container.close()
            container = None
            output.flush()
            os.fsync(output.fileno())
            output.close()
            output = None
            details = verify(folder / "recording.partial.mkv")
            state.update(details)
            if stop_reason == "stop":
                # Link publishes exclusively; never replace a previously published file.
                if sys.platform == "win32":
                    os.rename(folder / "recording.partial.mkv", folder / "recording.mkv")
                else:
                    os.link(folder / "recording.partial.mkv", folder / "recording.mkv")
                    (folder / "recording.partial.mkv").unlink()
                state.update(phase="completed", file="recording.mkv", error="")
            else:
                state.update(phase="interrupted", error="video_" + stop_reason)
        else:
            state.update(
                phase="cancelled", error=stop_reason if stop_reason.startswith("video_") else ""
            )
    except Exception as exc:
        # Human titles and provider data are never copied into diagnostics.
        state.update(
            phase="failed",
            error=str(exc) if str(exc).startswith("video_") else "video_capture_failed",
            diagnostic=type(exc).__name__,
        )
    finally:
        if control is not None:
            try:
                control.stop()
            except Exception:
                state.update(phase="failed", error="video_capture_stop_failed")
        try:
            if container is not None:
                container.close()
        except Exception:
            state.update(phase="failed", error="video_finalize_failed")
        try:
            if output is not None:
                output.flush()
                os.fsync(output.fileno())
                output.close()
        except Exception:
            state.update(phase="failed", error="video_finalize_failed")
        state.update(ended_at=time.time(), frames=frames, heartbeat=time.time())
        video_capture.atomic_state(folder, state)


def main():
    if os.environ.get("BLATERO_VIDEO_TRACE") == "1":
        import faulthandler

        faulthandler.dump_traceback_later(12, repeat=True)
    config = json.loads(sys.stdin.readline())
    commands = queue.Queue(maxsize=32)

    def listen():
        for line in sys.stdin:
            try:
                commands.put(json.loads(line), timeout=1)
            except (ValueError, queue.Full):
                pass
        commands.put({"action": "parent_closed"})

    record(config, commands, start_listener=listen)


if __name__ == "__main__":
    main()
