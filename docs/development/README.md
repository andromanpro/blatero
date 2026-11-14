# Карта исходников Blatero

[Обзор проекта](../../README.md) · [Пользовательская справка](../wiki/User-Guide.md) · [Версии](../../CHANGELOG.md)

Blatero разделён на Python-модули по функциям. При изучении кода можно начать
с нужного участка обработки данных.

## Звук и распознавание

| Файл | Назначение |
|---|---|
| [audio_capture.py](../../audio_capture.py) | Независимый захват аудио и передача PCM получателям |
| [live.py](../../live.py) | Координация микрофона, системного звука, записи и распознавания |
| [local_whisper.py](../../local_whisper.py) | Локальное распознавание Whisper |
| [speechkit_stream.py](../../speechkit_stream.py) | Потоковое распознавание Yandex SpeechKit |
| [transcript_events.py](../../transcript_events.py) | Первичный журнал реплик и читаемый транскрипт |

[Формат транскрипта](TRANSCRIPT_FORMAT.md) · [Модели разделения говорящих](DIARIZATION_MODELS.md)

## Подсказки, материалы и отчёт

| Файл | Назначение |
|---|---|
| [copilot.py](../../copilot.py) | Подсказки по разговору и подключённым материалам |
| [llm.py](../../llm.py) | Поставщики ИИ и общий выход к моделям |
| [workspace_context.py](../../workspace_context.py) | Подготовка контекста рабочей папки |
| [meeting_capture.py](../../meeting_capture.py) | Подключение контекста к начатой записи |
| [report.py](../../report.py) | Формирование отчёта |
| [report_review.py](../../report_review.py) | Проверка выводов перед сохранением результата |

## Проекты и знания

| Файл | Назначение |
|---|---|
| [project_store.py](../../project_store.py) | Карточки задач, статусы, основания и история |
| [project_api.py](../../project_api.py) | Локальный HTTP API проектов, задач и библиотеки, Bearer-ключи агентов |
| [knowledge_hub.py](../../knowledge_hub.py) | Хранение и поиск знаний |
| [knowledge_cli.py](../../knowledge_cli.py) | CLI поиска, чтения источников и предложений в базу знаний |
| [knowledge_worker.py](../../knowledge_worker.py) | Фоновый сбор и актуализация источников |
| [meeting_memory.py](../../meeting_memory.py) | Память договорённостей по проектам |
| [project_session_catalog.py](../../project_session_catalog.py) | Локальный импорт истории сессий агентов |

У импортёра истории рабочий каталог задаётся параметром `--workspace`.
По умолчанию используется родительская папка исходников приложения.

## Приватность и качество распознавания

| Файл | Назначение |
|---|---|
| [privacy.py](../../privacy.py) | Базовая очистка текста перед обращением к модели |
| [privacy_inspector.py](../../privacy_inspector.py) | Локальное распознавание имён, организаций и мест через Natasha |
| [workspace_privacy.py](../../workspace_privacy.py) | Просмотр и подтверждение отправки материалов рабочей папки |
| [quality_benchmark.py](../../quality_benchmark.py) | Ручная разметка эталона качества по архивным записям |
| [transcript_eval.py](../../transcript_eval.py) | Расчёт метрик транскрипта |
| [speaker_diarization.py](../../speaker_diarization.py) | Послевстречное разделение голосов и назначение имён |
| [speaker_profiles.py](../../speaker_profiles.py) | Локальный банк голосов и предложения имён |

[Аудио, говорящие и эталон качества](../wiki/Audio-and-Speakers.md) ·
[Приватность и провайдеры](../wiki/Privacy-and-Providers.md) ·
[Подключение агентов и работа с задачами](../wiki/Projects.md)

## Интерфейс и сборка

- [panel.py](../../panel.py) запускает FastAPI, WebSocket и веб-панель.
- [assets](../../assets) содержит интерфейс, стили и локальные ресурсы.
- [templates](../../templates) содержит HTML-шаблоны.
- [ci/build_release.py](../../ci/build_release.py) собирает подписанный пакет исходников приложения.
- [ci/build_windows_portable.py](../../ci/build_windows_portable.py) собирает Windows portable.
- [ci/check_public_content.py](../../ci/check_public_content.py) проверяет выбранные для публикации файлы.

Проверка публичного состава запускается из корня репозитория.

```text
python ci/check_public_content.py
```

Ключи поставщиков, данные встреч и рабочие базы создаются в каталоге данных
пользователя. Расположение программы и данных определяет
[app_paths.py](../../app_paths.py). Настройка описана в
[руководстве по установке](../wiki/Installation-Recovery-Updates.md).
