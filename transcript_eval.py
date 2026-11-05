"""Локальная оценка WER/DER/JER, каналов и межканального эхо-фильтра."""
from __future__ import annotations

import argparse
import datetime as dt
import itertools
import json
import os
import re
import time
import uuid
from pathlib import Path

from channel_echo import normalized_words
import transcript_events


FRAME_MS = 100
DER_COLLAR_MS = 250
_ANNOTATION_FIELDS = frozenset({
    "text", "start_ms", "end_ms", "source", "speaker_role", "speaker_id",
    "speaker_name", "status", "suppression_reason", "annotation_confidence",
    "annotation_note",
})
_ANNOTATION_SOURCES = frozenset({
    "microphone", "loopback", "synthetic", "manual", "import"})


def _utterances(records: list[dict], *, final_only: bool = True) -> list[dict]:
    result = [item for item in records
              if item.get("record_type") == "utterance"]
    if final_only:
        result = [item for item in result
                  if item.get("status", "final") == "final"]
    return sorted(result, key=lambda item: (
        int(item.get("start_ms", 0)), int(item.get("sequence", 0))))


def _edit_distance(reference: tuple[str, ...], hypothesis: tuple[str, ...]) -> int:
    previous = list(range(len(hypothesis) + 1))
    for row, left in enumerate(reference, 1):
        current = [row]
        for column, right in enumerate(hypothesis, 1):
            current.append(min(
                previous[column] + 1,
                current[column - 1] + 1,
                previous[column - 1] + (left != right)))
        previous = current
    return previous[-1]


def _timeline(events: list[dict]) -> tuple[dict[int, set[str]], dict[tuple, str]]:
    frames: dict[int, set[str]] = {}
    sources: dict[tuple[int, str], str] = {}
    for event in events:
        speaker = str(event.get("speaker_id") or event.get("speaker_role") or "unknown")
        source = str(event.get("source") or "unknown")
        start = max(0, int(event.get("start_ms", 0)))
        end = max(start + FRAME_MS, int(event.get("end_ms", start)))
        for frame in range(start // FRAME_MS, (end - 1) // FRAME_MS + 1):
            frames.setdefault(frame, set()).add(speaker)
            sources[(frame, speaker)] = source
    return frames, sources


def _exact_speaker_pairs(ref_speakers: list[str], hyp_speakers: list[str],
                         overlap: dict[tuple[str, str], int]) -> list[tuple[str, str]]:
    if len(ref_speakers) <= len(hyp_speakers):
        candidates = (list(zip(ref_speakers, selected)) for selected in
                      itertools.permutations(hyp_speakers, len(ref_speakers)))
    else:
        candidates = (list(zip(selected, hyp_speakers)) for selected in
                      itertools.permutations(ref_speakers, len(hyp_speakers)))
    best_pairs: list[tuple[str, str]] = []
    best_score = -1
    for pairs in candidates:
        score = sum(overlap[pair] for pair in pairs)
        if score > best_score:
            best_score, best_pairs = score, pairs
    return best_pairs


def _greedy_speaker_pairs(ref_speakers: list[str], hyp_speakers: list[str],
                          overlap: dict[tuple[str, str], int]) -> list[tuple[str, str]]:
    available_ref = set(ref_speakers)
    available_hyp = set(hyp_speakers)
    result = []
    for (ref, hyp), _score in sorted(
            overlap.items(), key=lambda item: item[1], reverse=True):
        if ref in available_ref and hyp in available_hyp:
            result.append((ref, hyp))
            available_ref.remove(ref)
            available_hyp.remove(hyp)
    return result


def _speaker_mapping(reference: dict[int, set[str]],
                     hypothesis: dict[int, set[str]]) -> dict[str, str]:
    ref_speakers = sorted(set().union(*reference.values()) if reference else set())
    hyp_speakers = sorted(set().union(*hypothesis.values()) if hypothesis else set())
    overlap = {
        (ref, hyp): sum(ref in reference.get(frame, set())
                        and hyp in hypothesis.get(frame, set())
                        for frame in set(reference) | set(hypothesis))
        for ref in ref_speakers for hyp in hyp_speakers
    }
    if not ref_speakers or not hyp_speakers:
        return {}
    if max(len(ref_speakers), len(hyp_speakers)) <= 8:
        best_pairs = _exact_speaker_pairs(ref_speakers, hyp_speakers, overlap)
    else:
        best_pairs = _greedy_speaker_pairs(ref_speakers, hyp_speakers, overlap)
    return {hyp: ref for ref, hyp in best_pairs}


def _collar_frames(reference: list[dict], collar_ms: int) -> set[int]:
    """Кадры около границ эталонных сегментов, исключаемые из DER/JER.

    Граница дискретизируется по центру кадра. Один общий scoring-mask соответствует
    принятому no-score collar: гипотеза внутри него также не считается false alarm.
    """
    if collar_ms <= 0:
        return set()
    result: set[int] = set()
    for event in reference:
        start = max(0, int(event.get("start_ms", 0)))
        end = max(start + FRAME_MS, int(event.get("end_ms", start)))
        for boundary in (start, end):
            first = max(0, (boundary - collar_ms) // FRAME_MS)
            last = (boundary + collar_ms - 1) // FRAME_MS
            for frame in range(first, last + 1):
                center = frame * FRAME_MS + FRAME_MS / 2
                if abs(center - boundary) < collar_ms:
                    result.add(frame)
    return result


def _timeline_counts(reference: list[dict], hypothesis: list[dict], *,
                     collar_ms: int = DER_COLLAR_MS) -> dict:
    ref_frames, ref_sources = _timeline(reference)
    hyp_frames, hyp_sources = _timeline(hypothesis)
    excluded = _collar_frames(reference, collar_ms)
    ref_frames = {frame: speakers for frame, speakers in ref_frames.items()
                  if frame not in excluded}
    hyp_frames = {frame: speakers for frame, speakers in hyp_frames.items()
                  if frame not in excluded}
    mapping = _speaker_mapping(ref_frames, hyp_frames)
    missed = false_alarm = confused = reference_time = 0
    channel_wrong = channel_paired = 0
    for frame in set(ref_frames) | set(hyp_frames):
        refs = ref_frames.get(frame, set())
        hyps = hyp_frames.get(frame, set())
        correct = sum(1 for hyp in hyps if mapping.get(hyp) in refs)
        reference_time += len(refs)
        missed += max(0, len(refs) - len(hyps))
        false_alarm += max(0, len(hyps) - len(refs))
        confused += max(0, min(len(refs), len(hyps)) - correct)
        for hyp in hyps:
            ref = mapping.get(hyp)
            if ref not in refs:
                continue
            channel_paired += 1
            channel_wrong += (
                hyp_sources.get((frame, hyp)) != ref_sources.get((frame, ref)))

    inverse = {ref: hyp for hyp, ref in mapping.items()}
    ref_speakers = sorted(set().union(*ref_frames.values()) if ref_frames else set())
    jer_sum = 0.0
    for ref in ref_speakers:
        hyp = inverse.get(ref)
        ref_active = {frame for frame, speakers in ref_frames.items()
                      if ref in speakers}
        hyp_active = ({frame for frame, speakers in hyp_frames.items()
                       if hyp in speakers} if hyp else set())
        union = len(ref_active | hyp_active)
        intersection = len(ref_active & hyp_active)
        jer_sum += 1.0 - intersection / max(1, union)
    return {
        "missed": missed,
        "false_alarm": false_alarm,
        "confused": confused,
        "reference_time": reference_time,
        "jer_sum": jer_sum,
        "jer_speakers": len(ref_speakers),
        "channel_wrong": channel_wrong,
        "channel_paired": channel_paired,
        "mapping": mapping,
        "der_collar_ms": collar_ms,
    }


def _echo_counts(reference: list[dict], hypothesis: list[dict]) -> dict:
    refs = {str(item.get("event_id")): item for item in reference
            if item.get("event_id")}
    hyps = {str(item.get("event_id")): item for item in hypothesis
            if item.get("event_id")}
    common = refs.keys() & hyps.keys()
    tp = fp = fn = reference_kept = 0
    for event_id in common:
        expected = refs[event_id].get("status", "final") == "suppressed"
        actual = hyps[event_id].get("status", "final") == "suppressed"
        tp += expected and actual
        fp += not expected and actual
        fn += expected and not actual
        reference_kept += not expected
    return {"echo_tp": tp, "echo_fp": fp, "echo_fn": fn,
            "echo_reference_kept": reference_kept,
            "echo_common": len(common)}


def _rates(counts: dict) -> dict:
    ref_words = counts["reference_words"]
    reference_time = counts["reference_time"]
    paired = counts["channel_paired"]
    tp, fp, fn = counts["echo_tp"], counts["echo_fp"], counts["echo_fn"]
    return {
        "wer": counts["word_errors"] / max(1, ref_words),
        "der": (counts["missed"] + counts["false_alarm"] + counts["confused"])
               / max(1, reference_time),
        "jer": counts["jer_sum"] / max(1, counts["jer_speakers"]),
        "channel_error_rate": counts["channel_wrong"] / max(1, paired),
        "channel_coverage": paired / max(1, reference_time),
        "echo_precision": tp / max(1, tp + fp),
        "echo_recall": tp / max(1, tp + fn),
        "false_suppression_rate": counts["echo_fp"] / max(
            1, counts["echo_reference_kept"]),
    }


def aggregate_scores(results: list[dict]) -> dict:
    """Объединить независимые результаты без усреднения процентов по файлам."""
    keys = (
        "reference_words", "hypothesis_words", "word_errors", "missed",
        "false_alarm", "confused", "reference_time", "jer_sum",
        "jer_speakers", "channel_wrong", "channel_paired", "echo_tp",
        "echo_fp", "echo_fn", "echo_reference_kept", "echo_common",
    )
    totals = dict.fromkeys(keys, 0)
    for result in results:
        counts = result.get("counts") if isinstance(result, dict) else None
        if not isinstance(counts, dict):
            raise ValueError("результат оценки не содержит счётчиков")
        for key in keys:
            totals[key] += counts[key]
    collars = {int(result.get("der_collar_ms", DER_COLLAR_MS))
               for result in results}
    if len(collars) > 1:
        raise ValueError("нельзя агрегировать DER с разным collar")
    collar_ms = next(iter(collars), DER_COLLAR_MS)
    return {**_rates(totals), "der_collar_ms": collar_ms, "counts": totals}


def score_records(hypothesis: list[dict], reference: list[dict], *,
                  allow_draft: bool = False,
                  der_collar_ms: int = DER_COLLAR_MS) -> dict:
    """Оценить уже загруженные журналы, включая отфильтрованный канал."""
    if (reference and reference[0].get("annotation_state") != "reviewed"
            and not allow_draft):
        raise ValueError("эталон ещё черновой; проверьте разметку и выполните finalize")
    hyp_final = _utterances(hypothesis)
    ref_final = _utterances(reference)
    ref_words = tuple(word for item in ref_final
                      for word in normalized_words(item.get("text", "")))
    hyp_words = tuple(word for item in hyp_final
                      for word in normalized_words(item.get("text", "")))
    counts = {
        "reference_words": len(ref_words),
        "hypothesis_words": len(hyp_words),
        "word_errors": _edit_distance(ref_words, hyp_words),
        **_timeline_counts(ref_final, hyp_final, collar_ms=der_collar_ms),
        **_echo_counts(_utterances(reference, final_only=False),
                       _utterances(hypothesis, final_only=False)),
    }
    collar_ms = int(counts.pop("der_collar_ms"))
    return {**_rates(counts), "der_collar_ms": collar_ms, "counts": counts}


def validate_reference_binding(hypothesis: list[dict], reference: list[dict],
                               *, hypothesis_name: str | None = None) -> None:
    """Убедиться, что reviewed-reference создан именно для этого журнала.

    Replay-производные имеют новый ``recording_id`` и оцениваются отдельно после
    проверки их исходного baseline. Поэтому эта граница применяется к первичной
    паре journal/reference, а не к произвольным производным транскриптам.
    """
    if (not hypothesis or hypothesis[0].get("record_type") != "recording"
            or not reference or reference[0].get("record_type") != "recording"):
        raise ValueError("пустая или повреждённая пара hypothesis/reference")
    hyp_header, ref_header = hypothesis[0], reference[0]
    expected_name = str(ref_header.get("reference_for") or "").strip()
    if not expected_name or Path(expected_name).name != expected_name:
        raise ValueError("эталон не содержит безопасную привязку reference_for")
    if hypothesis_name is not None and expected_name != Path(hypothesis_name).name:
        raise ValueError(
            f"эталон предназначен для {expected_name}, а не для "
            f"{Path(hypothesis_name).name}")
    for field, label in (("recording_id", "запись"), ("segment", "сегмент"),
                         ("started_at", "время начала")):
        expected = ref_header.get(field)
        actual = hyp_header.get(field)
        if expected in (None, "") or actual in (None, ""):
            raise ValueError(f"в паре отсутствует идентификатор: {label}")
        if str(expected) != str(actual):
            raise ValueError(f"эталон относится к другой записи: {label} не совпадает")


def score(hypothesis_path: Path, reference_path: Path,
          *, allow_draft: bool = False) -> dict:
    hypothesis = transcript_events.read_records(Path(hypothesis_path))
    reference = transcript_events.read_records(Path(reference_path))
    validate_reference_binding(
        hypothesis, reference, hypothesis_name=Path(hypothesis_path).name)
    return {"hypothesis": str(hypothesis_path),
            "reference": str(reference_path),
            **score_records(hypothesis, reference, allow_draft=allow_draft)}


def init_reference(hypothesis_path: Path, reference_path: Path) -> None:
    records = transcript_events.read_records(Path(hypothesis_path))
    if not records:
        raise ValueError("пустой transcript.jsonl")
    records[0] = {**records[0],
                  "reference_for": str(Path(hypothesis_path).name),
                  "annotation_state": "draft",
                  "annotation_note": (
                      "Проверьте text/start_ms/end_ms/source/speaker_id/status; "
                      "затем выполните finalize."),
                  "reference_created_at": dt.datetime.now().astimezone().isoformat(
                      timespec="milliseconds")}
    with Path(reference_path).open("x", encoding="utf-8", newline="") as output:
        for item in records:
            output.write(json.dumps(item, ensure_ascii=False) + "\n")


def finalize_reference(reference_path: Path) -> None:
    path = Path(reference_path)
    records = transcript_events.read_records(path)
    validate_reference(records)
    records[0]["annotation_state"] = "reviewed"
    records[0]["reference_reviewed_at"] = dt.datetime.now().astimezone().isoformat(
        timespec="milliseconds")
    tmp = path.with_name(path.name + ".tmp")
    with tmp.open("w", encoding="utf-8", newline="") as output:
        for item in records:
            output.write(json.dumps(item, ensure_ascii=False) + "\n")
    os.replace(tmp, path)


def _annotation_error(sequence: int, message: str) -> None:
    raise ValueError(f"некорректная правка sequence={sequence}: {message}")


def _validate_annotation_categories(event: dict, sequence: int) -> None:
    if event.get("speaker_role") not in {"Я", "Собеседник"}:
        _annotation_error(sequence, "speaker_role должен быть Я/Собеседник")
    if event.get("source") not in _ANNOTATION_SOURCES:
        _annotation_error(sequence, "неизвестный source")
    if event.get("status", "final") not in {"final", "suppressed"}:
        _annotation_error(sequence, "status должен быть final/suppressed")
    if not isinstance(event.get("text"), str) or not event["text"].strip():
        _annotation_error(sequence, "text должен быть непустой строкой")


def _validate_annotation_strings(event: dict, sequence: int) -> None:
    speaker_id = event.get("speaker_id")
    if (not isinstance(speaker_id, str)
            or not speaker_id.strip() or len(speaker_id) > 200):
        _annotation_error(
            sequence, "speaker_id должен быть непустой строкой до 200 символов")
    for field in ("speaker_name", "suppression_reason", "annotation_note"):
        value = event.get(field)
        if value is not None and (not isinstance(value, str) or len(value) > 1000):
            _annotation_error(sequence, f"{field} должен быть строкой до 1000 символов")


def _validate_annotation_time(event: dict, sequence: int) -> None:
    try:
        start = int(event.get("start_ms"))
        end = int(event.get("end_ms"))
    except (TypeError, ValueError) as exc:
        raise ValueError(
            f"некорректная правка sequence={sequence}: времена должны быть числами"
        ) from exc
    if start < 0 or end < start:
        _annotation_error(sequence, "ожидается 0 <= start_ms <= end_ms")


def _validate_annotation_confidence(event: dict, sequence: int) -> None:
    confidence = event.get("annotation_confidence")
    if (confidence is not None
            and (isinstance(confidence, bool)
                 or not isinstance(confidence, (int, float))
                 or not 0 <= float(confidence) <= 1)):
        _annotation_error(sequence, "annotation_confidence должна быть от 0 до 1")


def validate_annotation(event: dict, sequence: int) -> None:
    _validate_annotation_categories(event, sequence)
    _validate_annotation_strings(event, sequence)
    _validate_annotation_time(event, sequence)
    _validate_annotation_confidence(event, sequence)


def validate_reference(records: list[dict]) -> None:
    """Проверить весь эталон перед включением в агрегированные метрики."""
    if not records or records[0].get("record_type") != "recording":
        raise ValueError("пустой или повреждённый эталон")
    utterances = [item for item in records[1:]
                  if item.get("record_type") == "utterance"]
    if not utterances:
        raise ValueError("эталон не содержит реплик")
    event_ids = [str(item.get("event_id") or "") for item in utterances]
    sequences = [int(item.get("sequence") or 0) for item in utterances]
    if any(not re.fullmatch(r"[0-9a-f]{32,64}", value, re.IGNORECASE)
           for value in event_ids) or len(set(event_ids)) != len(event_ids):
        raise ValueError("event_id реплик должны быть непустыми и уникальными")
    if any(value <= 0 for value in sequences) or len(set(sequences)) != len(sequences):
        raise ValueError("sequence реплик должны быть положительными и уникальными")
    for event, sequence in zip(utterances, sequences):
        validate_annotation(event, sequence)


def _annotation_patch(path: Path) -> dict:
    patch = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(patch, dict) or not isinstance(patch.get("utterances"), dict):
        raise ValueError("patch должен содержать объект utterances")
    return patch


def _annotation_sequence(raw_sequence: object, by_sequence: dict[int, dict]) -> int:
    try:
        sequence = int(raw_sequence)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"некорректный sequence: {raw_sequence}") from exc
    if sequence not in by_sequence:
        raise ValueError(f"реплика sequence={sequence} не найдена")
    return sequence


def _apply_annotation_change(event: dict, changes: object, sequence: int) -> None:
    if not isinstance(changes, dict):
        raise ValueError(f"правка sequence={sequence} должна быть объектом")
    unknown = set(changes) - _ANNOTATION_FIELDS
    if unknown:
        raise ValueError(
            f"запрещённые поля sequence={sequence}: {sorted(unknown)}")
    validate_annotation({**event, **changes}, sequence)
    event.update(changes)


def write_records(path: Path, records: list[dict]) -> None:
    path = Path(path)
    tmp = path.with_name(path.name + "." + uuid.uuid4().hex + ".tmp")
    created = False
    try:
        with tmp.open("x", encoding="utf-8", newline="") as output:
            created = True
            for item in records:
                output.write(json.dumps(item, ensure_ascii=False) + "\n")
            output.flush()
            os.fsync(output.fileno())
        for attempt in range(5):
            try:
                os.replace(tmp, path)
                break
            except PermissionError:
                if attempt == 4:
                    raise
                # Windows readers/AV can briefly deny replacement. Retry these
                # exact bytes, not the edit or a generation/recognition request.
                time.sleep(.01 * 2**attempt)
    finally:
        if created:
            tmp.unlink(missing_ok=True)


def apply_annotation_patch(reference_path: Path, patch_path: Path) -> int:
    """Применить проверяемые правки по sequence к черновику эталона."""
    path = Path(reference_path)
    records = transcript_events.read_records(path)
    if not records or records[0].get("record_type") != "recording":
        raise ValueError("пустой или повреждённый эталон")
    patch = _annotation_patch(Path(patch_path))
    by_sequence = {int(item["sequence"]): item for item in records[1:]
                   if item.get("record_type") == "utterance"}
    for raw_sequence, changes in patch["utterances"].items():
        sequence = _annotation_sequence(raw_sequence, by_sequence)
        _apply_annotation_change(by_sequence[sequence], changes, sequence)
    note = str(patch.get("annotation_note") or "").strip()
    records[0]["annotation_state"] = "draft"
    if note:
        records[0]["annotation_note"] = note
    records[0]["annotation_updated_at"] = dt.datetime.now().astimezone().isoformat(
        timespec="milliseconds")
    write_records(path, records)
    return len(patch["utterances"])


def score_directory(root: Path, *, allow_draft: bool = False) -> dict:
    results = []
    for reference in sorted(Path(root).rglob("transcript*.reference.jsonl")):
        hypothesis = reference.with_name(
            reference.name.replace(".reference.jsonl", ".jsonl"))
        if hypothesis.exists():
            results.append(score(hypothesis, reference, allow_draft=allow_draft))
    if not results:
        raise ValueError("не найдены пары transcript*.jsonl + *.reference.jsonl")
    return {"files": len(results), "summary": aggregate_scores(results),
            "results": results}


def _print_rates(result: dict) -> None:
    values = result.get("summary", result)
    print(f"WER {values['wer']:.1%} · DER {values['der']:.1%} · "
          f"JER {values['jer']:.1%}")
    print(f"Канал: ошибка {values['channel_error_rate']:.1%}, "
          f"покрытие {values['channel_coverage']:.1%}")
    print(f"Эхо: precision {values['echo_precision']:.1%}, "
          f"recall {values['echo_recall']:.1%}, "
          f"ложное подавление {values['false_suppression_rate']:.1%}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    init = sub.add_parser("init", help="создать черновик ручного эталона")
    init.add_argument("hypothesis", type=Path)
    init.add_argument("reference", type=Path)
    finalize = sub.add_parser("finalize", help="пометить проверенный эталон")
    finalize.add_argument("reference", type=Path)
    annotate = sub.add_parser(
        "annotate", help="применить JSON-патч ручной разметки")
    annotate.add_argument("reference", type=Path)
    annotate.add_argument("patch", type=Path)
    one = sub.add_parser("score", help="оценить одну запись")
    one.add_argument("hypothesis", type=Path)
    one.add_argument("reference", type=Path)
    one.add_argument("--allow-draft", action="store_true")
    one.add_argument("--json", action="store_true")
    directory = sub.add_parser("score-dir", help="оценить весь эталонный набор")
    directory.add_argument("root", type=Path)
    directory.add_argument("--allow-draft", action="store_true")
    directory.add_argument("--json", action="store_true")
    args = parser.parse_args()
    if args.command == "init":
        init_reference(args.hypothesis, args.reference)
        print(f"Черновик эталона: {args.reference}")
    elif args.command == "finalize":
        finalize_reference(args.reference)
        print(f"Эталон подтверждён: {args.reference}")
    elif args.command == "annotate":
        changed = apply_annotation_patch(args.reference, args.patch)
        print(f"Размечено реплик: {changed}; эталон оставлен черновым")
    else:
        result = (score(args.hypothesis, args.reference,
                        allow_draft=args.allow_draft)
                  if args.command == "score" else
                  score_directory(args.root, allow_draft=args.allow_draft))
        if args.json:
            print(json.dumps(result, ensure_ascii=False, indent=2))
        else:
            _print_rates(result)


if __name__ == "__main__":
    main()
