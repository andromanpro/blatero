# Third-party notices

## Опциональная видеозапись Windows

Windows Capture 2.0.1 (MIT) получает кадры через Windows Graphics Capture:
<https://github.com/NiiightmareXD/windows-capture>.
Его Python-обёртка использует OpenCV (`opencv-python` 5.0.0.93) и NumPy.
Кодирование выполняется уже используемым PyAV 18.0.0 и библиотеками FFmpeg
его установленной сборки. Файлы лицензий этих пакетов и включённых кодеков
сохраняются в runtime; дополнительный список закреплён в `requirements-video.txt`.
Компонент не записывает микрофон и не отправляет видео во внешние сервисы.

## Автономные отчёты и справка

python-docx 1.2.0 (MIT) создаёт DOCX локально; markdown-it-py 4.0.0 (MIT) и
mdurl 0.1.2 (MIT) разбирают Markdown. Лицензии пакетов входят в runtime.
Экспорт не загружает внешние изображения и не требует Node.js или Office.

## Чтение изображений и старых документов

Pillow 13.0.0 используется локально для подготовки PNG, удаления метаданных и
закрашивания выбранных областей. Лицензия пакета включается в переносимую среду:
<https://github.com/python-pillow/Pillow>.
Для старых Office/Visio-файлов используется отдельно установленный LibreOffice;
он не добавлен в переносимую поставку Blatero: <https://www.libreoffice.org/>.

## Локальная проверка персональных данных

Natasha 1.6.0 (MIT) используется для локального распознавания имён и других
именованных сущностей: <https://github.com/natasha/natasha>.
Модели и словарь эмбеддингов входят в установленный пакет Natasha; во время
проверки пользовательских материалов отдельная загрузка моделей не выполняется.
Связанные зависимости закреплены в `requirements.lock`; лицензии установленных
пакетов включаются в состав переносимой среды. Качество зависит от языка и
текста и не гарантирует обнаружения всех персональных данных.

## Проверка подписанных релизов

Для Ed25519-подписи и проверки release-манифеста используется Python package
`cryptography` 50.0.1, распространяемый на условиях Apache License 2.0 или
BSD 3-Clause License: <https://github.com/pyca/cryptography>.

## Локальные модели

Blatero загружает эти компоненты только по явной команде пользователя и не
включает их веса в Git-репозиторий:

- faster-whisper и модели Systran/OpenAI Whisper — MIT,
  <https://github.com/SYSTRAN/faster-whisper>;
- Chatterbox Multilingual V3 — MIT,
  <https://github.com/resemble-ai/chatterbox> и
  <https://huggingface.co/ResembleAI/chatterbox>;
- sherpa-onnx — Apache-2.0,
  <https://github.com/k2-fsa/sherpa-onnx>;
- pyannote segmentation ONNX и 3D-Speaker embeddings — лицензии и источники
  закреплены вместе с SHA-256 в `speaker_diarization.py`.

Менеджер показывает эти сведения до установки. Полные тексты лицензий и model
cards в источниках имеют приоритет над краткой подписью в интерфейсе.

## OpenWhispr Meeting AEC Helper

Blatero может по явной команде пользователя загрузить бинарник
`meeting-aec-helper-v1.0.0` для Windows x64. Бинарник не входит в Git-репозиторий
Blatero и хранится локально в `.models/aec3/`.

- исходный код: <https://github.com/OpenWhispr/openwhispr/tree/main/native/meeting-aec-helper>;
- закреплённый релиз: <https://github.com/OpenWhispr/openwhispr/releases/tag/meeting-aec-helper-v1.0.0>;
- лицензия OpenWhispr: MIT, Copyright (c) 2024 OpenWhispr Team;
- WebRTC Audio Processing: BSD-style license, исходный проект
  <https://webrtc.googlesource.com/src/>.

### OpenWhispr MIT License

Copyright (c) 2024 OpenWhispr Team

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.

### WebRTC BSD License

Copyright (c) 2011, The WebRTC project authors. All rights reserved.

Redistribution and use in source and binary forms, with or without
modification, are permitted provided that the following conditions are met:

- Redistributions of source code must retain the above copyright notice,
  this list of conditions and the following disclaimer.
- Redistributions in binary form must reproduce the above copyright notice,
  this list of conditions and the following disclaimer in the documentation
  and/or other materials provided with the distribution.
- Neither the name of Google nor the names of its contributors may be used to
  endorse or promote products derived from this software without specific
  prior written permission.

THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE FOR
ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES
(INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES;
LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON
ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
(INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS
SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
