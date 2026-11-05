"""Подавление одной и той же реплики, распознанной на двух аудиоканалах."""
from __future__ import annotations

import inspect
import re
import threading
import time
from dataclasses import dataclass
from difflib import SequenceMatcher
from typing import Callable


_WORD = re.compile(r"[0-9a-zа-яё]+", re.IGNORECASE)


def normalized_words(text: str) -> tuple[str, ...]:
    return tuple(_WORD.findall(str(text).lower().replace("ё", "е")))


def echo_similarity(left: str, right: str) -> float:
    """Вернуть уверенность, что две STT-фразы описывают одно аудиособытие."""
    left_words = normalized_words(left)
    right_words = normalized_words(right)
    if min(len(left_words), len(right_words)) < 3:
        return 0.0
    left_text = " ".join(left_words)
    right_text = " ".join(right_words)
    if min(len(left_text), len(right_text)) < 12:
        return 0.0
    if left_text == right_text:
        return 1.0
    shorter, longer = sorted((left_text, right_text), key=len)
    if len(shorter) >= 18 and shorter in longer:
        return 0.98
    sequence = SequenceMatcher(None, left_text, right_text).ratio()
    left_set, right_set = set(left_words), set(right_words)
    token_overlap = len(left_set & right_set) / max(
        1, min(len(left_set), len(right_set)))
    if sequence >= 0.78 or (sequence >= 0.62 and token_overlap >= 0.72):
        return max(sequence, token_overlap * 0.95)
    return 0.0


@dataclass
class _Turn:
    received: float
    sequence: int
    speaker: str
    text: str
    metadata: dict | None = None


def _accepts_metadata(callback: Callable) -> bool:
    """Проверить поддержку emit(speaker, text, metadata) без пробного вызова."""
    try:
        parameters = list(inspect.signature(callback).parameters.values())
    except (TypeError, ValueError):
        return False
    if any(item.kind == inspect.Parameter.VAR_POSITIONAL for item in parameters):
        return True
    positional = [item for item in parameters if item.kind in (
        inspect.Parameter.POSITIONAL_ONLY,
        inspect.Parameter.POSITIONAL_OR_KEYWORD)]
    return len(positional) >= 3


def _capture_interval(metadata: dict | None) -> tuple[float, float] | None:
    if not isinstance(metadata, dict):
        return None
    try:
        start, end = float(metadata["start_ms"]), float(metadata["end_ms"])
    except (KeyError, TypeError, ValueError):
        return None
    if not (0 <= start < end < float("inf")):
        return None
    return start, end


def _same_audio_event(left: _Turn, right: _Turn, window: float) -> bool:
    first, second = _capture_interval(left.metadata), _capture_interval(right.metadata)
    if first is not None and second is not None:
        # Delivery can be delayed independently by either recognizer. Known,
        # disjoint capture intervals must NEVER be merged as textual echo.
        return max(first[0], second[0]) < min(first[1], second[1])
    return abs(left.received - right.received) <= window


class CrossChannelEchoFilter:
    """Ненадолго буферизует STT и оставляет loopback-копию двойной реплики.

    KTalk mute влияет только на отправку голоса в звонок. Физический микрофон
    Blatero продолжает работать и может акустически услышать наушники. Поэтому
    уверенное совпадение между ``Я`` и ``Собеседник`` считается межканальным
    эхом; системный loopback имеет приоритет. Короткие ответы не сравниваются.
    """

    def __init__(self, emit: Callable[[str, str], None], *, enabled: bool = True,
                 window_seconds: float = 2.2,
                 clock: Callable[[], float] | None = None,
                 autostart: bool = True, on_suppressed: Callable | None = None):
        self.emit = emit
        self._emit_metadata = _accepts_metadata(emit)
        self.on_suppressed = on_suppressed
        self._suppressed_metadata = bool(
            on_suppressed and _accepts_metadata(on_suppressed))
        self.enabled = bool(enabled)
        self.window_seconds = max(0.1, float(window_seconds))
        self.clock = clock or time.monotonic
        self._condition = threading.Condition()
        self._pending: list[_Turn] = []
        self._sequence = 0
        self._suppressed = 0
        self._closed = False
        self._publication_error = ""
        self._failed_turns: list[_Turn] = []
        self._thread: threading.Thread | None = None
        if self.enabled and autostart:
            self._thread = threading.Thread(
                target=self._run, daemon=True, name="cross-channel-echo")
            self._thread.start()

    @property
    def suppressed(self) -> int:
        with self._condition:
            return self._suppressed

    @property
    def publication_error(self) -> str:
        with self._condition:
            return self._publication_error

    @property
    def unconfirmed_count(self) -> int:
        with self._condition:
            return len(self._failed_turns) + len(self._pending)

    def _failed(self, error: Exception, turns: list[_Turn]) -> None:
        with self._condition:
            # Never retry a possibly committed append: the outcome may be unknown.
            # Retain the unconfirmed batch until shutdown/recovery from raw WAV.
            self._publication_error = self._publication_error or type(error).__name__
            self._failed_turns.extend(turns)
            self._condition.notify_all()

    def raise_if_failed(self) -> None:
        if self.publication_error:
            raise RuntimeError(
                "сохранение транскрипта прервано "
                f"({self.publication_error}); неподтверждённых реплик: "
                f"{self.unconfirmed_count}; требуется восстановление из WAV") from None

    def _emit_direct(self, speaker: str, text: str,
                     metadata: dict | None) -> None:
        if self._emit_metadata:
            self.emit(speaker, text, metadata)
        else:
            self.emit(speaker, text)

    def _opposite_echoes(self, turn: _Turn) -> list[_Turn]:
        return [
            pending for pending in self._pending
            if pending.speaker != turn.speaker
            and _same_audio_event(pending, turn, self.window_seconds)
            and echo_similarity(pending.text, turn.text) > 0
        ]

    def _prefer_guest_turn(self, turn: _Turn,
                           opposite: list[_Turn]) -> list[tuple[_Turn, float]]:
        candidates = opposite + [turn]
        earliest = min(candidates, key=lambda item: item.sequence)
        for pending in opposite:
            self._pending.remove(pending)
        self._pending.append(_Turn(
            min(item.received for item in candidates),
            earliest.sequence, turn.speaker, turn.text, turn.metadata))
        self._suppressed += len(opposite)
        return [(pending, echo_similarity(pending.text, turn.text))
                for pending in opposite]

    def _resolve_echo(self, turn: _Turn,
                      opposite: list[_Turn]) -> tuple[bool, list[tuple[_Turn, float]]]:
        if turn.speaker == "Собеседник":
            return True, self._prefer_guest_turn(turn, opposite)
        self._suppressed += 1
        similarity = max(echo_similarity(pending.text, turn.text)
                         for pending in opposite)
        return False, [(turn, similarity)]

    def _add_locked(self, turn: _Turn) -> tuple[bool, list[tuple[_Turn, float]]]:
        opposite = self._opposite_echoes(turn)
        if opposite:
            result = self._resolve_echo(turn, opposite)
        else:
            self._pending.append(turn)
            result = True, []
        self._condition.notify_all()
        return result

    def add(self, speaker: str, text: str, metadata: dict | None = None) -> bool:
        text = str(text).strip()
        if not text:
            return False
        self.raise_if_failed()
        if not self.enabled:
            try:
                self._emit_direct(speaker, text, metadata)
            except Exception as exc:
                self._failed(exc, [_Turn(self.clock(), 0, speaker, text, metadata)])
                self.raise_if_failed()
            return True
        with self._condition:
            self.raise_if_failed()
            if self._closed:
                return False
            now = self.clock()
            self._sequence += 1
            new_turn = _Turn(now, self._sequence, speaker, text, metadata)
            accepted, dropped = self._add_locked(new_turn)
        for index, (turn, similarity) in enumerate(dropped):
            try:
                self._emit_suppressed(turn, similarity)
            except Exception as exc:
                self._failed(exc, [item for item, _ in dropped[index:]])
                self.raise_if_failed()
        return accepted

    def _emit_suppressed(self, turn: _Turn, similarity: float) -> None:
        self._publish_suppressed(turn, similarity, "cross_channel_echo")

    def _publish_suppressed(self, turn: _Turn, similarity: float | None, reason: str) -> None:
        if self.on_suppressed is None:
            return
        metadata = dict(turn.metadata or {})
        metadata.update({
            "status": "suppressed",
            "suppression_reason": reason,
            "echo_similarity": round(float(similarity), 6) if similarity is not None else None,
        })
        if self._suppressed_metadata:
            self.on_suppressed(turn.speaker, turn.text, metadata)
        else:
            self.on_suppressed(turn.speaker, turn.text)

    def add_suppressed(self, speaker: str, text: str, metadata: dict | None,
                       reason: str) -> None:
        self.raise_if_failed()
        turn = _Turn(self.clock(), 0, speaker, text, metadata)
        try:
            self._publish_suppressed(turn, None, reason)
        except Exception as exc:
            self._failed(exc, [turn])
            self.raise_if_failed()
        with self._condition:
            self._suppressed += 1

    def _take_ready_locked(self) -> list[_Turn]:
        now = self.clock()
        ready = [turn for turn in self._pending
                 if self._closed or now - turn.received >= self.window_seconds]
        if ready:
            ready_ids = {id(turn) for turn in ready}
            self._pending = [turn for turn in self._pending
                             if id(turn) not in ready_ids]
        return sorted(ready, key=lambda turn: turn.sequence)

    def _emit_all(self, ready: list[_Turn]) -> None:
        if self.publication_error:
            with self._condition:
                self._failed_turns.extend(ready)
            self.raise_if_failed()
        for index, turn in enumerate(ready):
            try:
                if self._emit_metadata:
                    self.emit(turn.speaker, turn.text, turn.metadata)
                else:
                    self.emit(turn.speaker, turn.text)
            except Exception as exc:
                self._failed(exc, ready[index:])
                self.raise_if_failed()

    def flush(self) -> None:
        """Немедленно вывести накопленные реплики (также для unit-тестов)."""
        with self._condition:
            ready = sorted(self._pending, key=lambda turn: turn.sequence)
            self._pending.clear()
        self._emit_all(ready)

    def _run(self) -> None:
        try:
            self._run_pending()
        except Exception as exc:
            self._failed(exc, [])

    def _run_pending(self) -> None:
        while True:
            with self._condition:
                if self._publication_error:
                    return
                ready = self._take_ready_locked()
                if not ready:
                    if self._closed:
                        return
                    if self._pending:
                        due = (min(turn.received for turn in self._pending)
                               + self.window_seconds)
                        timeout = max(0.02, due - self.clock())
                    else:
                        timeout = None
                    self._condition.wait(timeout=timeout)
                    continue
            self._emit_all(ready)

    def close(self) -> None:
        if not self.enabled:
            self.raise_if_failed()
            return
        with self._condition:
            if self._closed:
                self.raise_if_failed()
                return
            self._closed = True
            self._condition.notify_all()
        if self._thread is not None:
            self._thread.join(timeout=max(3.0, self.window_seconds + 1.0))
            if self._thread.is_alive():
                self._failed(TimeoutError(), [])
        else:
            if not self.publication_error:
                self.flush()
        self.raise_if_failed()
