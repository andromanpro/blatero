"""Локальные читатели материалов: без запуска макросов и облачных запросов."""
from __future__ import annotations

import base64
import io
import json
import os
from pathlib import Path
import re
import subprocess
import zipfile

from defusedxml import ElementTree
from defusedxml.common import DefusedXmlException

from transcript_import import docx_text, pdf_text
import diagram_extract
import legacy_materials

IMAGE_SUFFIXES = frozenset({".png", ".jpg", ".jpeg", ".bmp", ".tif", ".tiff"})
DOCUMENT_SUFFIXES = (frozenset({".docx", ".pdf", ".xlsx", ".pptx", ".odt"})
                     | diagram_extract.SUFFIXES | frozenset(legacy_materials.TARGETS))
MAX_MEMBERS = 2500
MAX_UNPACKED_BYTES = 20 * 1024 * 1024
MAX_TEXT_CHARS = 1_000_000
OCR_TIMEOUT = 15

# Static program; document bytes enter through stdin, never PowerShell source.
# Windows PowerShell 5.1 is required for this WinRT bridge (not PowerShell 7).
_WINDOWS_OCR_SCRIPT = r"""
$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)
try {
  Add-Type -AssemblyName System.Runtime.WindowsRuntime
  $null = [Windows.Media.Ocr.OcrEngine,Windows.Foundation,ContentType=WindowsRuntime]
  $null = [Windows.Graphics.Imaging.BitmapDecoder,Windows.Foundation,ContentType=WindowsRuntime]
  $null = [Windows.Storage.Streams.InMemoryRandomAccessStream,Windows.Foundation,ContentType=WindowsRuntime]
  $null = [Windows.Globalization.Language,Windows.Foundation,ContentType=WindowsRuntime]
  $asTask = [System.WindowsRuntimeSystemExtensions].GetMethods() | Where-Object {
    $_.Name -eq 'AsTask' -and $_.IsGenericMethod -and
    $_.GetParameters().Count -eq 1 -and
    $_.GetParameters()[0].ParameterType.Name -eq 'IAsyncOperation`1'
  } | Select-Object -First 1
  function Await($operation, $resultType) {
    $task = $asTask.MakeGenericMethod($resultType).Invoke($null, @($operation))
    $task.Wait()
    return $task.Result
  }
  $ru = [Windows.Globalization.Language]::new('ru')
  $engine = [Windows.Media.Ocr.OcrEngine]::TryCreateFromLanguage($ru)
  if ($null -eq $engine) {
    $engine = [Windows.Media.Ocr.OcrEngine]::TryCreateFromUserProfileLanguages()
  }
  if ($null -eq $engine) { throw 'NO_LANGUAGE' }
  $bytes = [Convert]::FromBase64String([Console]::In.ReadToEnd())
  $stream = [Windows.Storage.Streams.InMemoryRandomAccessStream]::new()
  $writer = [Windows.Storage.Streams.DataWriter]::new($stream)
  $writer.WriteBytes($bytes)
  $null = Await ($writer.StoreAsync()) ([uint32])
  $writer.DetachStream() | Out-Null
  $writer.Dispose()
  $stream.Seek(0)
  $decoder = Await ([Windows.Graphics.Imaging.BitmapDecoder]::CreateAsync($stream)) ([Windows.Graphics.Imaging.BitmapDecoder])
  if ($decoder.FrameCount -ne 1) { throw 'MULTIFRAME' }
  $max = [Windows.Media.Ocr.OcrEngine]::MaxImageDimension
  if ($decoder.PixelWidth -gt $max -or $decoder.PixelHeight -gt $max -or
      ([double]$decoder.PixelWidth * $decoder.PixelHeight) -gt 20000000) { throw 'DIMENSIONS' }
  $bitmap = Await ($decoder.GetSoftwareBitmapAsync()) ([Windows.Graphics.Imaging.SoftwareBitmap])
  $result = Await ($engine.RecognizeAsync($bitmap)) ([Windows.Media.Ocr.OcrResult])
  $text = ($result.Lines | ForEach-Object { $_.Text }) -join "`n"
  if ($text.Length -gt 1000000) { throw 'TEXT_LIMIT' }
  @{text=$text; language=$engine.RecognizerLanguage.LanguageTag} | ConvertTo-Json -Compress
} catch {
  $code = $_.Exception.Message
  if ($code -notin @('NO_LANGUAGE','MULTIFRAME','DIMENSIONS','TEXT_LIMIT')) { $code = 'OCR_FAILED' }
  @{error=$code} | ConvertTo-Json -Compress
  exit 1
} finally {
  if ($null -ne $bitmap) { $bitmap.Dispose() }
  if ($null -ne $stream) { $stream.Dispose() }
}
"""


def image_text(raw: bytes) -> str:
    """Только текст изображения; не описание фотографии или смысла схемы."""
    if os.name != "nt":
        raise ValueError("локальное распознавание изображений доступно только в Windows")
    executable = (Path(os.environ.get("SystemRoot", r"C:\Windows"))
                  / "System32/WindowsPowerShell/v1.0/powershell.exe")
    command = [str(executable), "-NoProfile", "-NonInteractive", "-EncodedCommand",
               base64.b64encode(_WINDOWS_OCR_SCRIPT.encode("utf-16-le")).decode("ascii")]
    try:
        # Static local OCR bridge; document bytes are data on stdin.
        result = subprocess.run(  # nosec B603
            command, input=base64.b64encode(raw), stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, timeout=OCR_TIMEOUT,
            creationflags=subprocess.CREATE_NO_WINDOW)
    except subprocess.TimeoutExpired as exc:
        raise ValueError("распознавание изображения превысило 15 секунд") from exc
    except OSError as exc:
        raise ValueError("локальный модуль OCR Windows недоступен") from exc
    try:
        data = json.loads(result.stdout.decode("utf-8-sig"))
    except (UnicodeError, ValueError) as exc:
        raise ValueError("не удалось получить результат OCR Windows") from exc
    errors = {
        "NO_LANGUAGE": "установите компонент распознавания текста для языка в параметрах Windows",
        "MULTIFRAME": "многостраничное изображение нужно разделить на отдельные PNG/JPEG",
        "DIMENSIONS": "изображение слишком большое для OCR; уменьшите размер или разделите его",
        "TEXT_LIMIT": "в изображении слишком много текста",
    }
    if result.returncode or data.get("error"):
        raise ValueError(errors.get(data.get("error"),
                                    "OCR Windows не смог прочитать изображение"))
    text = str(data.get("text") or "").strip()
    if not text:
        raise ValueError("текст на изображении не найден; описание картинки не выполнялось")
    if len(text) > MAX_TEXT_CHARS:
        raise ValueError("извлечённый текст изображения слишком велик")
    return text


def _xml(archive: zipfile.ZipFile, name: str):
    try:
        return ElementTree.fromstring(archive.read(name))
    except (KeyError, ElementTree.ParseError, DefusedXmlException) as exc:
        raise ValueError("отсутствует или повреждён XML документа") from exc


def _xlsx_parts(archive: zipfile.ZipFile):
    ns = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
    names = archive.namelist()
    shared = []
    if "xl/sharedStrings.xml" in names:
        shared = ["".join(item.itertext()) for item in
                  _xml(archive, "xl/sharedStrings.xml").findall(ns + "si")]
    sheets = sorted(name for name in names if re.fullmatch(r"xl/worksheets/sheet\d+\.xml", name))
    if not sheets:
        raise ValueError("в XLSX нет доступных листов")
    for name in sheets:
        title_written = False
        for row in _xml(archive, name).iter(ns + "row"):
            cells = []
            for cell in row.findall(ns + "c"):
                kind = cell.get("t")
                value = cell.findtext(ns + "v", "")
                if kind == "s":
                    try:
                        index = int(value)
                        if index < 0:
                            raise ValueError("negative shared string index")
                        value = shared[index]
                    except (ValueError, IndexError) as exc:
                        raise ValueError("неверная ссылка на текст ячейки XLSX") from exc
                elif kind == "inlineStr":
                    value = "".join(node.text or "" for node in cell.iter(ns + "t"))
                formula = cell.findtext(ns + "f")
                if formula is not None:
                    value = f"формула: {formula}; сохранённое значение: {value or 'нет'}"
                if value:
                    cells.append(f"{cell.get('r', '?')}: {value}")
            if cells:
                if not title_written:
                    yield f"Лист: {name} (формулы не пересчитываются)"
                    title_written = True
                yield " | ".join(cells)


def _office_parts(archive: zipfile.ZipFile, suffix: str):
    if suffix == ".xlsx":
        yield from _xlsx_parts(archive)
    elif suffix == ".pptx":
        names = [name for name in archive.namelist()
                 if re.fullmatch(r"ppt/slides/slide\d+\.xml", name)]
        if not names:
            raise ValueError("в PPTX нет доступных слайдов")
        for name in sorted(names, key=lambda item: int(re.search(r"(\d+)\.xml", item)[1])):
            title_written = False
            ns = "{http://schemas.openxmlformats.org/drawingml/2006/main}"
            for paragraph in _xml(archive, name).iter(ns + "p"):
                text = "".join(node.text or "" for node in paragraph.iter(ns + "t"))
                if text.strip():
                    if not title_written:
                        yield f"Слайд: {name}"
                        title_written = True
                    yield text
    else:
        ns = "{urn:oasis:names:tc:opendocument:xmlns:text:1.0}"
        for node in _xml(archive, "content.xml").iter():
            if node.tag in {ns + "p", ns + "h"}:
                yield "".join(node.itertext())


def office_text(raw: bytes, suffix: str) -> str:
    try:
        with zipfile.ZipFile(io.BytesIO(raw)) as archive:
            members = archive.infolist()
            if (len(members) > MAX_MEMBERS
                    or sum(item.file_size for item in members) > MAX_UNPACKED_BYTES):
                raise ValueError("распакованный документ слишком велик")
            if len({item.filename for item in members}) != len(members):
                raise ValueError("документ содержит повторяющиеся ZIP-записи")
            chunks, size = [], 0
            for part in _office_parts(archive, suffix):
                size += len(part) + 1
                if size > MAX_TEXT_CHARS:
                    raise ValueError("извлечённый текст документа слишком велик")
                chunks.append(part)
            return "\n".join(chunks)
    except (zipfile.BadZipFile, OSError, RuntimeError, NotImplementedError) as exc:
        raise ValueError("документ повреждён или защищён паролем") from exc


def extract(raw: bytes, suffix: str) -> str:
    if suffix in legacy_materials.TARGETS:
        raw, suffix = legacy_materials.convert(raw, suffix)
    if suffix in diagram_extract.SUFFIXES:
        return diagram_extract.extract(raw, suffix)
    if suffix in IMAGE_SUFFIXES:
        return image_text(raw)
    if suffix == ".docx":
        text = docx_text(raw)
    elif suffix == ".pdf":
        text = pdf_text(raw, max_pages=100, max_chars=MAX_TEXT_CHARS)
    else:
        text = office_text(raw, suffix)
    if not text.strip():
        raise ValueError("нет доступного текста; сканы и встроенные картинки нужно сохранить отдельно для OCR")
    return text


def unsupported_reason(suffix: str) -> str:
    if suffix in {".doc", ".xls", ".ppt", ".rtf"}:
        return "сохраните в DOCX, XLSX, PPTX или TXT — старый формат не поддерживается"
    if suffix in {".zip", ".7z", ".rar", ".tar", ".gz"}:
        return "архив не распаковывается автоматически; выберите папку с извлечёнными материалами"
    if suffix in {".epf", ".erf", ".cf"}:
        return "бинарный файл 1С: нужны текстовая выгрузка исходников или описание"
    if suffix in {".wav", ".mp3", ".mp4", ".webm", ".m4a"}:
        return "аудио и видео разбираются в разделе разбора записи; добавьте сюда транскрипт"
    return "формат пока не поддерживается; сохраните содержимое как текст, PDF или изображение PNG/JPEG"
