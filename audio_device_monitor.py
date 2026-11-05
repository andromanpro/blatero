"""Устойчивые локальные события изменения WASAPI-аудиомаршрута."""
from __future__ import annotations

import datetime as dt
import threading
import time
from collections.abc import Callable


InventoryReader = Callable[[], dict]
_PERSISTENT_STATES = {"missing", "default_changed", "inventory_error"}


def _names(values: object) -> tuple[str, ...]:
    if not isinstance(values, (list, tuple, set)):
        return ()
    return tuple(sorted({str(value).strip() for value in values if str(value).strip()},
                        key=str.casefold))


def _inventory(value: dict | None, *, mic: str = "", output: str = "") -> dict:
    raw = value if isinstance(value, dict) else {}
    mics = (_names(raw.get("mics")) if "mics" in raw
            else ((mic,) if mic else ()))
    outputs = (_names(raw.get("outputs")) if "outputs" in raw
               else ((output,) if output else ()))
    return {
        "mics": mics,
        "outputs": outputs,
        "default_mic": str(raw.get("default_mic") or ""),
        "default_output": str(raw.get("default_output") or ""),
    }


class AudioDeviceMonitor:
    """Сравнивать снимки Core Audio без автоматической смены активного канала."""

    def __init__(self, reader: InventoryReader, *, mic_selector: str | int,
                 output_selector: str, active_mic: str, active_output: str,
                 clock: Callable[[], float] = time.monotonic,
                 notice_seconds: float = 12.0):
        self.reader = reader
        self.clock = clock
        self.notice_seconds = max(1.0, float(notice_seconds))
        self._lock = threading.Lock()
        self._event_id = 0
        self._event_at = 0.0
        self._event_signature: tuple = ()
        self._state = "ok"
        self._roles: tuple[str, ...] = ()
        self._message = "Аудиоустройства без изменений"
        self._changed_at = ""
        self._counts = {"added_mics": 0, "removed_mics": 0,
                        "added_outputs": 0, "removed_outputs": 0}
        self._last_base_state = "ok"
        self._missing_roles: set[str] = set()
        self._mic_selector = mic_selector
        self._output_selector = output_selector
        self._active_mic = str(active_mic or "")
        self._active_output = str(active_output or "")
        try:
            first = reader()
        except Exception:
            first = None
        self._inventory = _inventory(
            first, mic=self._active_mic, output=self._active_output)

    @staticmethod
    def _timestamp() -> str:
        return dt.datetime.now().astimezone().isoformat(timespec="milliseconds")

    @staticmethod
    def _role_message(roles: set[str] | tuple[str, ...]) -> str:
        names = []
        if "mic" in roles:
            names.append("микрофон")
        if "output" in roles:
            names.append("выход системного звука")
        return " и ".join(names) or "аудиомаршрут"

    def _emit(self, state: str, roles: set[str], message: str,
              counts: dict, now: float) -> None:
        signature = (state, tuple(sorted(roles)), message,
                     self._active_mic, self._active_output,
                     self._mic_selector, self._output_selector,
                     self._inventory["mics"], self._inventory["outputs"],
                     self._inventory["default_mic"],
                     self._inventory["default_output"])
        if signature == self._event_signature:
            return
        self._event_signature = signature
        self._event_id += 1
        self._event_at = now
        self._state = state
        self._roles = tuple(sorted(roles))
        self._message = message
        self._changed_at = self._timestamp()
        self._counts = counts

    def poll(self, *, mic_selector: str | int, output_selector: str,
             active_mic: str, active_output: str) -> dict:
        """Прочитать новый снимок. Ошибка инвентаризации не роняет REC."""
        with self._lock:
            now = self.clock()
            previous_inventory = self._inventory
            previous_active = (self._active_mic, self._active_output)
            previous_base_state = self._last_base_state
            self._mic_selector = mic_selector
            self._output_selector = output_selector
            self._active_mic = str(active_mic or "")
            self._active_output = str(active_output or "")
            try:
                current = _inventory(
                    self.reader(), mic=self._active_mic,
                    output=self._active_output)
            except Exception:
                self._last_base_state = "inventory_error"
                self._emit(
                    "inventory_error", set(),
                    "Windows не отвечает на запрос списка аудиоустройств",
                    {key: 0 for key in self._counts}, now)
                return self._snapshot(now)

            self._inventory = current
            mic_names = set(current["mics"])
            output_names = set(current["outputs"])
            missing = set()
            if self._active_mic and self._active_mic not in mic_names:
                missing.add("mic")
            if self._active_output and self._active_output not in output_names:
                missing.add("output")
            returned = self._missing_roles - missing
            self._missing_roles = missing

            default_changed = set()
            if (mic_selector == "auto" and current["default_mic"]
                    and current["default_mic"] != self._active_mic):
                default_changed.add("mic")
            if (output_selector == "auto" and current["default_output"]
                    and current["default_output"] != self._active_output):
                default_changed.add("output")

            route_changed = set()
            if previous_active[0] != self._active_mic:
                route_changed.add("mic")
            if previous_active[1] != self._active_output:
                route_changed.add("output")
            counts = {
                "added_mics": len(mic_names - set(previous_inventory["mics"])),
                "removed_mics": len(set(previous_inventory["mics"]) - mic_names),
                "added_outputs": len(
                    output_names - set(previous_inventory["outputs"])),
                "removed_outputs": len(
                    set(previous_inventory["outputs"]) - output_names),
            }
            # Default важен только для каналов с selector=auto. При явном выборе
            # пользователь не должен получать шум из-за чужой системной смены.
            inventory_changed = any(counts.values())

            if missing:
                state, roles = "missing", missing
                message = f"Отключён {self._role_message(roles)}"
            elif default_changed:
                state, roles = "default_changed", default_changed
                message = ("Системное устройство по умолчанию изменилось: "
                           f"{self._role_message(roles)}")
            elif returned:
                state, roles = "returned", returned
                message = f"Снова доступен {self._role_message(roles)}"
            elif route_changed:
                state, roles = "route_changed", route_changed
                message = f"Переключён {self._role_message(roles)}"
            elif previous_base_state == "inventory_error":
                state, roles = "inventory_restored", set()
                message = "Список аудиоустройств снова доступен"
            elif inventory_changed:
                state, roles = "inventory_changed", set()
                message = "Состав аудиоустройств Windows изменился"
            else:
                state, roles = "ok", set()
                message = "Аудиоустройства без изменений"
            self._last_base_state = state
            if state != "ok":
                self._emit(state, roles, message, counts, now)
            elif (self._state in _PERSISTENT_STATES
                  or now - self._event_at >= self.notice_seconds):
                self._state = "ok"
                self._roles = ()
                self._message = message
                self._counts = {key: 0 for key in counts}
            return self._snapshot(now)

    def _snapshot(self, now: float) -> dict:
        state = self._state
        if (state not in _PERSISTENT_STATES and state != "ok"
                and now - self._event_at >= self.notice_seconds):
            state = "ok"
        return {
            "state": state,
            "event_id": self._event_id,
            "changed_at": self._changed_at,
            "roles": list(self._roles if state != "ok" else ()),
            "message": self._message if state != "ok" else
                       "Аудиоустройства без изменений",
            "action_required": state in {"missing", "default_changed"},
            "mic_available": self._active_mic in set(self._inventory["mics"]),
            "output_available": self._active_output in set(
                self._inventory["outputs"]),
            "mics": ["auto", *self._inventory["mics"]],
            "outputs": ["auto", *self._inventory["outputs"]],
            **self._counts,
        }

    def snapshot(self) -> dict:
        with self._lock:
            return self._snapshot(self.clock())
