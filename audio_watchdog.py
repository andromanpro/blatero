"""Локальный аудиосторож: правила, рекомендации и журнал переходов REC."""
from __future__ import annotations

import datetime as dt
import json
import math
import time
from pathlib import Path


SCHEMA_VERSION = 1
SEVERITY_RANK = {"notice": 1, "warning": 2, "critical": 3}
SAMPLE_INTERVAL_SECONDS = 10.0
DEFAULT_THRESHOLDS = {
    "stt_queue_warning_ms": 5_000,
    "stt_queue_critical_ms": 15_000,
    "stt_latency_warning_ms": 6_000,
    "stt_latency_critical_ms": 12_000,
    "wav_backlog_warning_ms": 2_000,
    "wav_backlog_critical_ms": 10_000,
    "clipping_warning_ratio": 0.005,
    "clipping_critical_ratio": 0.03,
}
_THRESHOLD_PAIRS = (
    ("stt_queue_warning_ms", "stt_queue_critical_ms", 500.0, 120_000.0),
    ("stt_latency_warning_ms", "stt_latency_critical_ms", 500.0, 120_000.0),
    ("wav_backlog_warning_ms", "wav_backlog_critical_ms", 250.0, 120_000.0),
    ("clipping_warning_ratio", "clipping_critical_ratio", 0.0001, 0.5),
)


def normalize_thresholds(value: object = None) -> dict:
    """Validate a complete/partial watchdog profile without accepting extras."""
    if value is None:
        return dict(DEFAULT_THRESHOLDS)
    if not isinstance(value, dict):
        raise ValueError("audio_guard_thresholds: ожидается объект")
    unknown = set(value) - set(DEFAULT_THRESHOLDS)
    if unknown:
        raise ValueError(
            f"audio_guard_thresholds: неизвестные поля {sorted(unknown)}")
    result = dict(DEFAULT_THRESHOLDS)
    for key, raw in value.items():
        if isinstance(raw, bool) or not isinstance(raw, (int, float)):
            raise ValueError(f"audio_guard_thresholds.{key}: ожидается число")
        number = float(raw)
        if not math.isfinite(number):
            raise ValueError(f"audio_guard_thresholds.{key}: число некорректно")
        result[key] = number
    for warning, critical, minimum, maximum in _THRESHOLD_PAIRS:
        if not minimum <= result[warning] < result[critical] <= maximum:
            raise ValueError(
                f"audio_guard_thresholds: нужно {minimum:g} <= {warning} < "
                f"{critical} <= {maximum:g}")
    return {
        key: (round(number, 6) if key.endswith("_ratio") else int(number))
        for key, number in result.items()
    }


def _number(value: object, default: float = 0.0) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return default
    number = float(value)
    return number if math.isfinite(number) else default


def _issue(code: str, severity: str, title: str, detail: str, action: str,
           verify: str, action_kind: str, *, hold: float = 0.0,
           clear_hold: float = 0.0,
           evidence: dict | None = None) -> dict:
    return {
        "code": code, "severity": severity, "title": title,
        "detail": detail, "action": action, "verify": verify,
        "action_kind": action_kind, "hold": max(0.0, float(hold)),
        "clear_hold": max(0.0, float(clear_hold)),
        "evidence": evidence or {},
    }


class AudioWatchdog:
    """Преобразовать числовые live-метрики в устойчивые рекомендации."""

    def __init__(self, journal: Path, thresholds: object = None):
        self.journal = Path(journal)
        self.thresholds = normalize_thresholds(thresholds)
        self._pending: dict[str, float] = {}
        self._clearing: dict[str, float] = {}
        self._active: dict[str, dict] = {}
        self._last_drop_total = 0
        self._last_drop_at: float | None = None
        self._last_sample_at: float | None = None
        self._started_at = dt.datetime.now().astimezone().isoformat(
            timespec="milliseconds")

    @staticmethod
    def _timestamp() -> str:
        return dt.datetime.now().astimezone().isoformat(timespec="milliseconds")

    def _append(self, record: dict) -> None:
        try:
            # Не воскрешать удалённую во время REC папку встречи. Runtime всегда
            # получает уже существующую сессию; отсутствие каталога безопасно
            # означает, что диагностический журнал записать больше некуда.
            if not self.journal.parent.is_dir():
                return
            if self.journal.is_symlink():
                return
            if self.journal.resolve(strict=False).parent != \
                    self.journal.parent.resolve():
                return
            if not self.journal.exists():
                header = {
                    "schema_version": SCHEMA_VERSION,
                    "record_type": "audio_watch",
                    "started_at": self._started_at,
                    "thresholds": self.thresholds,
                }
                with self.journal.open("x", encoding="utf-8", newline="") as output:
                    output.write(json.dumps(header, ensure_ascii=False) + "\n")
            with self.journal.open("a", encoding="utf-8", newline="") as output:
                output.write(json.dumps(record, ensure_ascii=False) + "\n")
        except OSError:
            # Наблюдатель не должен останавливать захват даже при проблеме диска.
            return

    def _drop_is_recent(self, raw: dict, now: float) -> tuple[bool, int]:
        total = max(0, int(_number(raw.get("stt_dropped_chunks"))))
        if total < self._last_drop_total:
            # Горячая смена STT создаёт новый счётчик потерь.
            self._last_drop_total = total
            self._last_drop_at = None
        if total > self._last_drop_total:
            self._last_drop_at = now
        self._last_drop_total = max(self._last_drop_total, total)
        return bool(total and self._last_drop_at is not None
                    and now - self._last_drop_at < 12), total

    def _candidates(self, raw: dict, now: float) -> list[dict]:
        result = []
        elapsed = max(0.0, _number(raw.get("elapsed_seconds"),
                                   _number(raw.get("sec"))))
        wav_error = bool(raw.get("wav_write_error"))
        capture_failed = bool(raw.get("error")) or (
            raw.get("healthy") is False and not wav_error)
        if capture_failed:
            result.append(_issue(
                "capture_failure", "critical", "Аудиоканал оборвался",
                "Один из каналов больше не подтверждает захват. WAV до момента сбоя сохранён.",
                "Остановите REC, переподключите устройство, выберите его в настройках звука и начните новый сегмент.",
                "После нового старта обе дорожки должны двигаться, а красная ошибка — исчезнуть.",
                "open_audio"))

        device = raw.get("device_change")
        if not isinstance(device, dict):
            device = {}
        device_state = str(device.get("state") or "ok")
        raw_device_roles = device.get("roles")
        if not isinstance(raw_device_roles, (list, tuple, set)):
            raw_device_roles = []
        device_roles = {str(role) for role in raw_device_roles
                        if role in {"mic", "output"}}
        event_id = max(0, int(_number(device.get("event_id"))))
        device_evidence = {"event_id": event_id, "state": device_state}
        role_labels = {"mic": "Микрофон", "output": "Выход системного звука"}
        if device_state == "missing":
            for role in sorted(device_roles):
                label = role_labels[role]
                result.append(_issue(
                    f"device_missing_{role}", "critical", f"{label} отключён",
                    (f"{label} исчез из списка WASAPI. Звук до момента события "
                     "остаётся в текущем WAV."),
                    ("Переподключите устройство, откройте настройки звука и "
                     "явно выберите нужный маршрут. Blatero не переключится на "
                     "другое устройство без вашего выбора."),
                    ("Устройство должно появиться в списке; после переключения "
                     "соответствующая дорожка должна снова двигаться."),
                    "open_audio", hold=1.5,
                    evidence={**device_evidence, "role": role}))
        elif device_state == "default_changed":
            for role in sorted(device_roles):
                label = role_labels[role]
                result.append(_issue(
                    f"device_default_{role}", "warning",
                    f"Изменён системный маршрут: {label.lower()}",
                    ("Windows выбрала другое устройство по умолчанию, но текущий "
                     "канал Blatero оставлен прежним."),
                    ("Откройте настройки звука и подтвердите, какое устройство "
                     "должно использоваться для этой встречи."),
                    "Подпись маршрута и индикатор нужной дорожки должны совпасть.",
                    "open_audio", hold=1,
                    evidence={**device_evidence, "role": role}))
        elif device_state == "inventory_error":
            result.append(_issue(
                "device_inventory_error", "warning",
                "Windows не отвечает о состоянии устройств",
                "Запрос списка WASAPI временно завершился ошибкой; текущий захват не остановлен.",
                "Не меняйте маршрут вслепую. Откройте настройки звука и обновите список через несколько секунд.",
                "Список микрофонов и выходов должен снова открыться без ошибки.",
                "open_audio", hold=2, evidence=device_evidence))
        elif device_state in {
                "returned", "route_changed", "inventory_changed",
                "inventory_restored"}:
            titles = {
                "returned": "Аудиоустройство снова доступно",
                "route_changed": "Аудиомаршрут переключён",
                "inventory_changed": "Состав аудиоустройств изменился",
                "inventory_restored": "Список аудиоустройств восстановлен",
            }
            result.append(_issue(
                f"device_{device_state}", "notice", titles[device_state],
                "Blatero обновил локальный список WASAPI, не меняя канал автоматически.",
                "Если устройство меняли вы, проверьте обе дорожки. Иначе оставьте текущий маршрут.",
                "Подписи микрофона и выхода должны соответствовать выбранным устройствам.",
                "open_audio", clear_hold=1,
                evidence={**device_evidence, "roles": sorted(device_roles)}))

        if wav_error:
            result.append(_issue(
                "wav_write_failure", "critical", "WAV больше не записывается",
                "Поток звука идёт, но запись на диск завершилась ошибкой.",
                "Остановите REC, проверьте свободное место и доступ к папке встречи. Не удаляйте уже созданный WAV.",
                "В новом сегменте счётчик отставания WAV должен оставаться около нуля.",
                "open_results"))

        stt_label = str(raw.get("stt") or "")
        if "не загрузился" in stt_label.casefold():
            result.append(_issue(
                "stt_unavailable", "critical", "Распознавание не запустилось",
                "Сырой WAV продолжает писаться, но новые реплики не попадут в транскрипт.",
                "Выберите меньшую локальную модель или переключите движок распознавания; WAV продолжит записываться без остановки.",
                "После переключения статус должен показать активный Whisper или SpeechKit.",
                "open_stt"))

        recent_drop, dropped = self._drop_is_recent(raw, now)
        if recent_drop:
            result.append(_issue(
                "stt_dropped", "critical", "Распознавание теряет аудиоблоки",
                f"STT не успел обработать {dropped} блоков. Сырой WAV при этом сохраняется.",
                "Переключитесь на меньшую модель Whisper или другой STT. После встречи прогоните WAV через Replay Lab.",
                "Счётчик потерь не должен расти 12 секунд — тогда предупреждение снимется автоматически.",
                "open_stt", evidence={"dropped_chunks": dropped}))

        queue_ms = max(0, int(_number(raw.get("stt_queue_ms"))))
        queue_warning = self.thresholds["stt_queue_warning_ms"]
        queue_critical = self.thresholds["stt_queue_critical_ms"]
        if queue_ms >= queue_warning:
            loading = "загружается" in stt_label.casefold()
            severity = ("critical" if queue_ms >= queue_critical else
                        "notice" if loading else "warning")
            title = "Whisper готовится" if loading and queue_ms < queue_critical else \
                "Распознавание отстаёт"
            result.append(_issue(
                "stt_backlog", severity, title,
                f"В очереди STT накопилось примерно {queue_ms / 1000:.1f} с аудио.",
                ("Подождите окончания загрузки; WAV уже пишется. Если очередь растёт, выберите меньшую модель."
                 if loading and queue_ms < 15_000 else
                 "Выберите меньшую модель Whisper или переключите STT прямо во время записи."),
                (f"Очередь должна опуститься ниже {queue_warning / 1000:g} секунд "
                 "и оставаться там не менее трёх секунд."),
                "open_stt", hold=3, clear_hold=3,
                evidence={"queue_ms": queue_ms}))

        latency_ms = max(0, int(_number(raw.get("stt_latency_ms"))))
        result_age = max(0, int(_number(raw.get("stt_result_age_ms"), 999_999)))
        latency_warning = self.thresholds["stt_latency_warning_ms"]
        latency_critical = self.thresholds["stt_latency_critical_ms"]
        if latency_ms >= latency_warning and result_age <= 15_000:
            severity = "critical" if latency_ms >= latency_critical else "warning"
            result.append(_issue(
                "stt_latency", severity, "Текст приходит с задержкой",
                f"Последняя готовая реплика появилась через {latency_ms / 1000:.1f} с после звука.",
                "Уменьшите модель Whisper или временно переключите распознавание; WAV продолжает писаться без задержки.",
                (f"Следующая реплика должна появиться быстрее чем за "
                 f"{latency_warning / 1000:g} секунд."),
                "open_stt", evidence={"latency_ms": latency_ms}))

        if raw.get("transcript_write_error"):
            result.append(_issue(
                "transcript_write_error", "critical", "Сохранение транскрипта прервано",
                "Не все распознанные реплики сохранены. Исходный WAV записывается отдельно.",
                "После встречи восстановите транскрипт из WAV в разделе разбора аудио.",
                "Проверьте восстановленный текст перед созданием отчёта.",
                "open_results"))
        if raw.get("device_gaps"):
            result.append(_issue(
                "device_change_gap", "warning", "В записи была смена аудиоустройства",
                "При переключении физического устройства был перерыв захвата.",
                "При разборе встречи проверьте участок смены устройства.",
                "Времена переключений сохранены в диагностике встречи.",
                "open_results", hold=0))
        if raw.get("audio_processor_failed"):
            result.append(_issue(
                "audio_filter_disabled", "warning", "Аудиофильтр отключён после ошибки",
                "Распознавание получает исходный PCM без этого фильтра. WAV не изменяется.",
                "Проверьте звук и состояние очистки эха после встречи.",
                "При следующей записи фильтр должен снова обрабатывать микрофон.",
                "open_audio", hold=0))

        wav_backlog = max(0, int(_number(raw.get("wav_backlog_ms"))))
        wav_warning = self.thresholds["wav_backlog_warning_ms"]
        wav_critical = self.thresholds["wav_backlog_critical_ms"]
        if wav_backlog >= wav_warning and not wav_error:
            severity = "critical" if wav_backlog >= wav_critical else "warning"
            result.append(_issue(
                "wav_backlog", severity, "Диск не успевает за записью",
                f"Буфер WAV отстаёт примерно на {wav_backlog / 1000:.1f} с.",
                "Закройте тяжёлые операции с диском и проверьте свободное место в папке встречи.",
                (f"Отставание должно вернуться ниже {wav_warning / 1000:g} секунд "
                 "и оставаться там две секунды."),
                "open_results", hold=2, clear_hold=2,
                evidence={"backlog_ms": wav_backlog}))

        for channel, label in (("me", "микрофона"), ("guest", "системного звука")):
            ratio = max(0.0, _number(raw.get(f"{channel}_clipping_ratio")))
            clipping_warning = self.thresholds["clipping_warning_ratio"]
            clipping_critical = self.thresholds["clipping_critical_ratio"]
            if ratio < clipping_warning:
                continue
            severity = "critical" if ratio >= clipping_critical else "warning"
            result.append(_issue(
                f"clipping_{channel}", severity,
                f"Перегрузка {label}",
                f"За последние пять секунд ограничено {ratio:.1%} сэмплов — слова могут искажаться.",
                "Уменьшите громкость/усиление устройства или отодвиньте микрофон от рта.",
                ("Говорите пять секунд обычным голосом: доля перегрузки должна "
                 f"стать меньше {clipping_warning:.1%}."),
                "open_audio", hold=1.5, clear_hold=1.5,
                evidence={"clipping_ratio": round(ratio, 5)}))

        me_activity = max(0.0, _number(raw.get("me_activity")))
        guest_activity = max(0.0, _number(raw.get("guest_activity")))
        if elapsed >= 45 and guest_activity < 0.5 and me_activity >= 3:
            result.append(_issue(
                "guest_silent", "warning", "Не слышу собеседников",
                "Микрофон работает, но системная дорожка почти пустая.",
                "Выберите в Blatero тот же физический выход, который использует приложение звонка, и включите в нём тестовый звук.",
                "Зелёная дорожка должна начать двигаться; предупреждение снимется после 0,5 с сигнала.",
                "open_audio"))
        if elapsed >= 60 and me_activity < 0.5 and guest_activity >= 8:
            result.append(_issue(
                "microphone_silent", "warning", "Микрофон не подтверждён",
                "Системный звук слышен, но микрофонная дорожка почти пустая.",
                "Проверьте выбранный микрофон и разрешение Windows. Mute в приложении звонка не отключает захват Blatero.",
                "Скажите фразу обычным голосом: голубая дорожка должна двигаться.",
                "open_audio"))

        aec_enabled = raw.get("aec_enabled") is True
        requested = str(raw.get("aec_requested_backend") or "off")
        backend = str(raw.get("aec_backend") or "off")
        if (aec_enabled and requested in {"auto", "native"}
                and backend == "correlation"):
            result.append(_issue(
                "aec_fallback", "notice", "AEC работает в резервном режиме",
                "WebRTC AEC3 недоступен, поэтому используется безопасный корреляционный фильтр.",
                "После встречи откройте проверку звука и установите/проверьте AEC3. Запись останавливать не нужно.",
                "Статус AEC сменится на AEC3 после установки и нового запуска REC.",
                "open_audio", hold=5))
        captured = max(0, int(_number(raw.get("aec_capture_frames"))))
        if aec_enabled and elapsed >= 20 and me_activity >= 3 and captured == 0:
            result.append(_issue(
                "aec_inactive", "warning", "AEC не обрабатывает микрофон",
                "Подавление эха включено, но не получило ни одного микрофонного блока.",
                "Откройте настройки звука, проверьте обе дорожки и перезапустите REC новым сегментом.",
                "Счётчик AEC должен начать расти, когда вы говорите.",
                "open_audio", hold=3))
        return result

    def _sample(self, raw: dict, now: float, state: str) -> None:
        """Persist a privacy-safe numeric slice for later threshold calibration."""
        if self._last_sample_at is None:
            self._last_sample_at = now
            return
        if now - self._last_sample_at < SAMPLE_INTERVAL_SECONDS:
            return
        self._last_sample_at = now
        integer_fields = (
            "stt_queue_ms", "stt_dropped_chunks", "stt_latency_ms",
            "stt_result_age_ms", "wav_backlog_ms", "aec_capture_frames",
            "aec_processed_frames",
            "stt_queue_me_ms", "stt_queue_guest_ms", "stt_inflight_ms",
            "stt_buffered_ms", "stt_inference_ms", "stt_wait_ms",
        )
        ratio_fields = (
            "me_clipping_ratio", "guest_clipping_ratio", "me_activity",
            "guest_activity",
            "stt_rtf",
        )
        values = {key: max(0, int(_number(raw.get(key))))
                  for key in integer_fields}
        values.update({key: round(max(0.0, _number(raw.get(key))), 6)
                       for key in ratio_fields})
        self._append({
            "schema_version": SCHEMA_VERSION,
            "record_type": "audio_sample",
            "occurred_at": self._timestamp(),
            "elapsed_ms": max(0, round(_number(
                raw.get("elapsed_seconds"), _number(raw.get("sec"))) * 1000)),
            "state": state,
            "healthy": raw.get("healthy") is not False,
            "aec_enabled": raw.get("aec_enabled") is True,
            **values,
        })

    def _transition(self, candidates: list[dict], now: float) -> None:
        by_code = {item["code"]: item for item in candidates}
        for code in tuple(self._pending):
            if code not in by_code:
                self._pending.pop(code, None)
        for code, item in by_code.items():
            if code in self._active:
                self._clearing.pop(code, None)
                previous = self._active[code]
                self._active[code] = item
                if previous.get("severity") != item.get("severity"):
                    self._append({
                        "schema_version": SCHEMA_VERSION,
                        "record_type": "audio_issue", "state": "updated",
                        "occurred_at": self._timestamp(),
                        **{key: item[key] for key in (
                            "code", "severity", "title", "evidence")},
                    })
                continue
            since = self._pending.setdefault(code, now)
            if now - since < item["hold"]:
                continue
            self._pending.pop(code, None)
            self._active[code] = item
            self._append({
                "schema_version": SCHEMA_VERSION,
                "record_type": "audio_issue", "state": "opened",
                "occurred_at": self._timestamp(),
                **{key: item[key] for key in (
                    "code", "severity", "title", "evidence")},
            })
        for code in tuple(self._active):
            if code in by_code:
                continue
            previous = self._active[code]
            since = self._clearing.setdefault(code, now)
            if now - since < previous.get("clear_hold", 0.0):
                continue
            self._clearing.pop(code, None)
            self._active.pop(code)
            self._append({
                "schema_version": SCHEMA_VERSION,
                "record_type": "audio_issue", "state": "resolved",
                "occurred_at": self._timestamp(),
                **{key: previous[key] for key in (
                    "code", "severity", "title")},
            })

    def observe(self, raw: dict, *, now: float | None = None) -> dict:
        current = time.monotonic() if now is None else float(now)
        self._transition(self._candidates(raw, current), current)
        issues = sorted(
            ({key: value for key, value in item.items()
              if key not in {"hold", "clear_hold"}}
             for item in self._active.values()),
            key=lambda item: (-SEVERITY_RANK[item["severity"]], item["code"]))
        state = max((item["severity"] for item in issues),
                    key=lambda value: SEVERITY_RANK[value], default="ok")
        if state == "ok":
            summary = "Звук под контролем"
        elif state == "notice":
            summary = issues[0]["title"]
        else:
            count = sum(item["severity"] == state for item in issues)
            summary = issues[0]["title"] + (f" · ещё {count - 1}" if count > 1 else "")
        self._sample(raw, current, state)
        return {
            "state": state, "summary": summary, "issues": issues,
            "active_count": len(issues), "updated_at": self._timestamp(),
        }

    def close(self) -> None:
        self._append({
            "schema_version": SCHEMA_VERSION,
            "record_type": "audio_watch_stop",
            "occurred_at": self._timestamp(),
            "active_codes": sorted(self._active),
        })
