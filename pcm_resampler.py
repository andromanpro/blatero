"""Потоковый ресемплинг mono signed PCM16 без deprecated ``audioop``.

Позиция следующего выходного отсчёта хранится как целая рациональная фаза.
Поэтому разбиение одного и того же потока на произвольные чанки не меняет
результат и не накапливает временной дрейф.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass
class PCM16ResampleState:
    source_rate: int
    target_rate: int
    input_frames: int = 0
    next_output_numerator: int = 0
    previous_sample: int | None = None


def _rate(value: int, label: str) -> int:
    try:
        rate = int(value)
    except (TypeError, ValueError):
        raise ValueError(f"{label} должен быть целым числом") from None
    if rate <= 0:
        raise ValueError(f"{label} должен быть больше нуля")
    return rate


def resample_pcm16_mono(
        data: bytes, source_rate: int, target_rate: int,
        state: PCM16ResampleState | None = None,
) -> tuple[bytes, PCM16ResampleState]:
    """Линейно преобразовать mono little-endian PCM16, сохранив фазу потока.

    Целочисленное интерполирование намеренно округляется вниз. Это повторяет
    историческое поведение ``audioop.ratecv`` и не создаёт скачок уровня при
    обновлении существующих установок.
    """
    source_rate = _rate(source_rate, "source_rate")
    target_rate = _rate(target_rate, "target_rate")
    if len(data) % 2:
        raise ValueError("PCM16-чанк содержит неполный отсчёт")
    if state is None:
        state = PCM16ResampleState(source_rate, target_rate)
    elif (state.source_rate != source_rate
          or state.target_rate != target_rate):
        raise ValueError("состояние ресемплера относится к другой частоте")
    if not data:
        return b"", state

    samples = np.frombuffer(data, dtype="<i2").astype(np.int64)
    first_global = state.input_frames
    if state.previous_sample is None:
        window = samples
        window_start = first_global
    else:
        window = np.empty(len(samples) + 1, dtype=np.int64)
        window[0] = state.previous_sample
        window[1:] = samples
        window_start = first_global - 1

    last_global = first_global + len(samples) - 1
    last_numerator = last_global * target_rate
    next_numerator = state.next_output_numerator
    if next_numerator > last_numerator:
        output = b""
    else:
        count = (last_numerator - next_numerator) // source_rate + 1
        positions = (next_numerator
                     + np.arange(count, dtype=np.int64) * source_rate)
        left_global, fraction = np.divmod(positions, target_rate)
        left = left_global - window_start
        right = np.minimum(left + 1, len(window) - 1)
        values = (
            window[left] * (target_rate - fraction)
            + window[right] * fraction
        ) // target_rate
        output = values.astype("<i2").tobytes()
        state.next_output_numerator += int(count) * source_rate

    state.input_frames += len(samples)
    state.previous_sample = int(samples[-1])
    return output, state
