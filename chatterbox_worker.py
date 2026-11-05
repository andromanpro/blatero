"""Изолированный постоянный worker Chatterbox.

Основное приложение работает в лёгком .venv. Этот процесс запускается из
.venv-tts, один раз загружает модель и принимает JSON-команды через stdin.
Обычный вывод зависимостей игнорируется родителем; протокол помечен префиксом.
"""
from __future__ import annotations

import json
import hashlib
import os
import sys
import traceback
from pathlib import Path

PREFIX = "BLATERO_JSON "


def reply(payload: dict) -> None:
    print(PREFIX + json.dumps(payload, ensure_ascii=False), flush=True)


def main() -> None:
    os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")
    import torch
    import torchaudio as ta
    from chatterbox.mtl_tts import ChatterboxMultilingualTTS

    # Не занимать все ядра: параллельно должны жить панель, запись и Whisper.
    torch.set_num_threads(max(1, min(8, (os.cpu_count() or 4) // 2)))
    # Не откатываться молча на legacy V2: она может вместо русской фразы
    # генерировать бессмысленные слоги, которые формально остаются валидным WAV.
    try:
        model = ChatterboxMultilingualTTS.from_pretrained(
            device="cpu", t3_model="v3")
    except TypeError as exc:
        raise RuntimeError(
            "установлена старая Chatterbox без multilingual V3; "
            "переустановите requirements-chatterbox.txt") from exc
    model_version = "multilingual-v3"
    reply({"type": "ready", "model": model_version, "device": "cpu"})

    for line in sys.stdin:
        try:
            request = json.loads(line)
            request_id = str(request.get("id", ""))
            text = str(request["text"]).strip()
            reference = Path(request["reference"]).resolve()
            output = Path(request["output"]).resolve()
            if not text or len(text) > 4000:
                raise ValueError("текст должен содержать от 1 до 4000 символов")
            if not reference.is_file() or reference.suffix.lower() != ".wav":
                raise ValueError("эталон голоса не найден")
            output.parent.mkdir(parents=True, exist_ok=True)
            # Стабильная пониженная температура уменьшает случайные слоги и
            # делает кэш воспроизводимым между перезапусками worker.
            seed = int.from_bytes(
                hashlib.sha256(text.encode("utf-8")).digest()[:4], "big")
            torch.manual_seed(seed)
            wav = model.generate(
                text, audio_prompt_path=str(reference), language_id="ru",
                exaggeration=0.5, cfg_weight=0.3, temperature=0.6,
                repetition_penalty=1.2, top_p=0.9)
            ta.save(str(output), wav.cpu(), model.sr,
                    encoding="PCM_S", bits_per_sample=16)
            reply({"type": "result", "id": request_id, "ok": True,
                   "sample_rate": int(model.sr)})
        except Exception as exc:
            reply({"type": "result", "id": locals().get("request_id", ""),
                   "ok": False, "error": str(exc),
                   "detail": traceback.format_exc(limit=2)})


if __name__ == "__main__":
    main()
