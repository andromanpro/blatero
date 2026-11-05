"""Локальная временная шкала транскрипта с переходом к исходному аудио."""
from __future__ import annotations

import datetime as dt
import argparse
import html
import json
import re
from pathlib import Path

import transcript_events


_JOURNAL = re.compile(r"transcript(?:-\d+)?\.jsonl", re.IGNORECASE)
_REFERENCE = re.compile(
    r"transcript(?:-\d+)?\.reference\.jsonl", re.IGNORECASE)
_ANY_JOURNAL = re.compile(
    r"transcript(?:-\d+)?(?:\.[a-z0-9_-]+)*\.jsonl", re.IGNORECASE)
_OUTPUT = re.compile(
    r"evidence(?:\.(?:reference|diarized))?\.html", re.IGNORECASE)
_STAMP = re.compile(r"(?<!\])\[(\d{2}:\d{2}:\d{2})\](?!\()")
_REPORT_STAMP_LINK = re.compile(
    r"[ \t]*\[\d{2}:\d{2}:\d{2}\]\(evidence\.html#[^)]+\)")
_REPORT_PLAIN_STAMP = re.compile(
    r"[ \t]*\[\d{2}:\d{2}:\d{2}"
    r"(?:\s*[-–—]\s*\d{2}:\d{2}:\d{2})?\]")
DIARIZED_OUTPUT = "evidence.diarized.html"


def _journals(sdir: Path, *, reference: bool = False) -> list[Path]:
    pattern = _REFERENCE if reference else _JOURNAL
    return sorted((path for path in Path(sdir).glob("transcript*.jsonl")
                   if pattern.fullmatch(path.name)),
                  key=lambda path: transcript_events.segment_number(
                      Path(path.name.replace(".reference.jsonl", ".md"))))


def _entries(sdir: Path, *, reference: bool = False,
             journal_name: str | None = None) -> list[dict]:
    result = []
    if journal_name is not None:
        if (Path(journal_name).name != journal_name
                or not _ANY_JOURNAL.fullmatch(journal_name)):
            raise ValueError("недопустимое имя журнала")
        journals = [Path(sdir) / journal_name]
    else:
        journals = _journals(sdir, reference=reference)
    for journal in journals:
        records = transcript_events.read_records(journal)
        if not records:
            continue
        for event in records[1:]:
            if (event.get("record_type") != "utterance"
                    or event.get("status", "final") != "final"):
                continue
            stamp = dt.datetime.fromisoformat(str(event["captured_at"]))
            sequence = int(event.get("sequence", 0))
            segment = int(event.get("segment", 1))
            result.append({
                **event,
                "clock": stamp.strftime("%H:%M:%S"),
                "anchor": f"t-{stamp:%H%M%S}-{segment}-{sequence}",
            })
    return result


def link_report_timestamps(markdown: str, entries: list[dict]) -> str:
    """Сделать точные timestamp-ссылки кликабельными и добавить общий индекс."""
    anchors = {}
    for item in entries:
        anchors.setdefault(str(item["clock"]), str(item["anchor"]))

    def replace(match: re.Match) -> str:
        clock = match.group(1)
        anchor = anchors.get(clock)
        return (f"[{clock}](evidence.html#{anchor})" if anchor
                else match.group(0))

    linked = _STAMP.sub(replace, markdown)
    if entries and "(evidence.html" not in linked:
        linked = linked.rstrip() + (
            "\n\n## Доказательства\n\n"
            "[Открыть временную шкалу и исходные аудиофрагменты]"
            "(evidence.html).\n")
    return linked


def remove_report_timestamps(markdown: str) -> str:
    """Убрать доказательные таймкоды из обычной версии отчёта."""
    cleaned = _REPORT_STAMP_LINK.sub("", markdown)
    cleaned = _REPORT_PLAIN_STAMP.sub("", cleaned)
    return re.sub(r"[ \t]+([.,;:])", r"\1", cleaned)


def _timeline_output_name(output_name: str | None, reference: bool) -> str:
    checked = output_name or (
        "evidence.reference.html" if reference else "evidence.html")
    if Path(checked).name != checked or not _OUTPUT.fullmatch(checked):
        raise ValueError("недопустимое имя временной шкалы")
    return checked


def _effective_speaker(item: dict, splits: list[dict]) -> str:
    raw = str(item.get("speaker_id") or "unknown")
    start_ms = int(item.get("start_ms", 0))
    candidates = [split for split in splits
                  if split.get("source") == raw
                  and int(split.get("start_ms", 0)) <= start_ms]
    if not candidates:
        return raw
    return str(max(candidates, key=lambda split: int(
        split.get("start_ms", 0)))["speaker_id"])


def _speaker_examples(sdir: Path, entries: list[dict],
                      speaker_map: dict | None) -> tuple[list[str], dict]:
    splits = list((speaker_map or {}).get("splits") or [])
    mapped_speakers = dict((speaker_map or {}).get("speakers") or {})
    speaker_ids = sorted(mapped_speakers or {
        str(item.get("speaker_id") or "unknown"): {} for item in entries})
    candidates = {speaker_id: [] for speaker_id in speaker_ids}
    for item in entries:
        target = _effective_speaker(item, splits)
        audio_name = str(item.get("audio_file") or "")
        if target in candidates and audio_name and (sdir / audio_name).is_file():
            candidates[target].append(item)
    examples = {}
    for speaker_id, items in candidates.items():
        # A full, clear sentence is more useful for voice identification than
        # the first accidental "угу". Short clips remain as a fallback.
        def quality(item: dict) -> tuple[int, float, int, int]:
            start_ms = max(0, int(item.get("start_ms", 0)))
            end_ms = max(start_ms, int(item.get("end_ms", start_ms)))
            duration_ms = end_ms - start_ms
            text_length = len(re.sub(r"\s+", " ", str(
                item.get("text") or "")).strip())
            confidence = transcript_events.event_confidence(item)
            confidence_value = (float(confidence)
                                if isinstance(confidence, (int, float)) else 0.0)
            useful = int(1500 <= duration_ms <= 10000 and text_length >= 12)
            return (useful, confidence_value, min(text_length, 180),
                    min(duration_ms, 10000))

        selected = sorted(items, key=quality, reverse=True)[:3]
        examples[speaker_id] = sorted(
            selected, key=lambda item: int(item.get("start_ms", 0)))
    return speaker_ids, examples


def _audio_button(sdir: Path, item: dict) -> str:
    audio_name = str(item.get("audio_file") or "")
    if not audio_name or not (sdir / audio_name).is_file():
        return '<span class="no-audio">аудио недоступно</span>'
    start_ms = max(0, int(item.get("start_ms", 0)))
    end_ms = max(start_ms + 500, int(item.get("end_ms", start_ms + 8000)))
    return (f'<button class="play" data-file="{html.escape(audio_name, quote=True)}" '
            f'data-start="{start_ms / 1000:.3f}" data-end="{end_ms / 1000:.3f}">'
            "▶ фрагмент</button>")


def _speaker_color(speaker: str) -> int:
    digits = speaker[len(speaker.rstrip("0123456789")):]
    return int(digits) % 8 if digits else 0


def _split_action(item: dict, speaker: str, output_name: str) -> str:
    if output_name != DIARIZED_OUTPUT:
        return ""
    return (f'<button class="split-speaker" data-speaker="'
            f'{html.escape(speaker, quote=True)}" data-start="'
            f'{max(0, int(item.get("start_ms", 0)))}">'
            'с этой реплики — новый голос</button>')


def _evidence_card(sdir: Path, item: dict, output_name: str) -> str:
    confidence = transcript_events.event_confidence(item)
    confidence_text = (f" · confidence {float(confidence):.0%}"
                       if isinstance(confidence, (int, float)) else "")
    speaker = str(item.get("speaker_id") or "unknown")
    start_ms = max(0, int(item.get("start_ms", 0)))
    return (
        f'<article id="{item["anchor"]}" class="speaker-{_speaker_color(speaker)}">'
        f'<div class="meta"><a href="#{item["anchor"]}">'
        f'{html.escape(str(item["clock"]))}</a> · '
        f'{html.escape(str(item.get("speaker_role") or "спикер"))} · '
        f'<strong class="speaker-label" '
        f'data-speaker="{html.escape(speaker, quote=True)}" '
        f'data-start="{start_ms}">{html.escape(speaker)}</strong> · '
        f'{html.escape(str(item.get("source") or "unknown"))}'
        f'{html.escape(confidence_text)}</div>'
        f'<p>{html.escape(str(item.get("text") or ""))}</p>'
        f'{_audio_button(sdir, item)}{_split_action(item, speaker, output_name)}'
        '</article>')


def _timeline_heading(output_name: str, reference: bool) -> tuple[str, str]:
    if output_name == DIARIZED_OUTPUT:
        return ("Проверка кластеров голосов",
                "Прослушайте смены SPEAKER_NN перед присвоением имён. Кластеры "
                "анонимны и могут ошибаться; файлы никуда не отправляются.")
    if output_name == "evidence.reference.html" or reference:
        return ("Проверка эталонной разметки",
                "Проверьте текст, время, роль и источник каждой реплики по аудио. "
                "Файлы никуда не отправляются.")
    return ("Временная шкала доказательств",
            "Локальный индекс: переходите к реплике и запускайте запись с её "
            "приблизительного начала. Файлы никуда не отправляются.")


def _sample_buttons(speaker_id: str, examples: list[dict]) -> str:
    if not examples:
        return '<span class="no-audio">нет подходящих аудиофрагментов</span>'
    buttons = []
    for index, item in enumerate(examples, 1):
        start_ms = max(0, int(item.get("start_ms", 0)))
        raw_end_ms = int(item.get("end_ms", start_ms + 8000))
        end_ms = max(start_ms + 800, min(raw_end_ms, start_ms + 10000))
        duration = max(1, round((end_ms - start_ms) / 1000))
        excerpt = re.sub(r"\s+", " ", str(item.get("text") or "")).strip()
        title = f"{speaker_id}, пример {index}: {excerpt[:140]}"
        buttons.append(
            f'<button class="play example" data-file="'
            f'{html.escape(str(item.get("audio_file") or ""), quote=True)}" '
            f'data-start="{start_ms / 1000:.3f}" data-end="{end_ms / 1000:.3f}" '
            f'data-label="{html.escape(speaker_id, quote=True)} · пример {index}" '
            f'title="{html.escape(title, quote=True)}">'
            f'▶ пример {index} · {duration} с</button>')
    return (
        f'<button class="play-all" type="button" aria-label="Прослушать все примеры '
        f'{html.escape(speaker_id, quote=True)}">▶ прослушать все</button>'
        + "".join(buttons))


def _speaker_review_row(speaker_id: str, speaker_ids: list[str],
                        examples: dict, ordinal: int) -> str:
    merge_options = ['<option value="">не объединять</option>']
    merge_options.extend(
        f'<option value="{html.escape(other, quote=True)}">'
        f'{html.escape(other)}</option>'
        for other in speaker_ids if other != speaker_id)
    return (
        f'<div class="speaker-row speaker-{_speaker_color(speaker_id)}" data-speaker="'
        f'{html.escape(speaker_id, quote=True)}">'
        f'<div class="speaker-identity"><strong>Голос {ordinal}</strong>'
        f'<code>{html.escape(speaker_id)}</code>'
        '<span class="speaker-suggestion">ещё не сопоставлен</span>'
        '<button class="apply-suggestion" hidden>подставить имя</button></div>'
        '<label>Имя в этой встрече<input class="speaker-name" maxlength="80" '
        'placeholder="например, Александр"></label>'
        '<label>Сторона<select class="speaker-role">'
        '<option value="Собеседник">другой участник</option>'
        '<option value="Я">мой голос</option></select></label>'
        f'<label>Объединить с<select class="speaker-merge">'
        f'{"".join(merge_options)}</select></label>'
        f'<div class="speaker-examples"><div class="speaker-example-label">'
        '<strong>Проверка на слух</strong><small>короткие реплики остановятся сами</small>'
        '</div><div class="speaker-samples">'
        f'{_sample_buttons(speaker_id, examples.get(speaker_id, []))}'
        '</div><button class="enroll-speaker">запомнить голос для будущих встреч</button>'
        '</div></div>')


def _speaker_review_html(speaker_ids: list[str], examples: dict) -> str:
    rows = "".join(_speaker_review_row(speaker_id, speaker_ids, examples, index)
                   for index, speaker_id in enumerate(speaker_ids, 1))
    return (
        '<section id="speaker-review"><h2>Переименовать говорящих</h2>'
        '<div class="speaker-review-guide">'
        '<p><strong>Для этой встречи:</strong> прослушайте примеры, укажите имя и '
        'сторону, при необходимости объедините ошибочно разделённые голоса и '
        'сохраните. Банк голосов для этого не нужен.</p>'
        '<p><strong>Для будущих встреч:</strong> после ввода имени можно отдельно '
        'запомнить голос. Тогда Blatero сможет предложить имя в следующий раз, '
        'но применит его только после вашего подтверждения.</p></div>'
        '<div class="speaker-bank-actions">'
        '<button id="identify-speakers">Предложить имена из банка (необязательно)</button>'
        '<label class="bank-consent"><input id="speaker-bank-consent" '
        'type="checkbox"> Подтверждаю право и согласие на создание локального '
        'голосового отпечатка выбранного человека</label></div>'
        f'{rows}<div class="review-actions">'
        '<button id="save-speakers">Сохранить имена и использовать в транскрипте</button>'
        '<span id="speaker-status" class="intro">Загрузка…</span>'
        '</div></section>')


def build(sdir: Path, *, reference: bool = False,
          journal_name: str | None = None,
          output_name: str | None = None,
          speaker_map: dict | None = None) -> tuple[Path | None, list[dict]]:
    """Создать автономный evidence.html; все данные и аудио остаются локально."""
    sdir = Path(sdir)
    entries = _entries(
        sdir, reference=reference, journal_name=journal_name)
    if not entries:
        return None, []
    output_name = _timeline_output_name(output_name, reference)
    speaker_ids, examples = _speaker_examples(sdir, entries, speaker_map)
    cards = [_evidence_card(sdir, item, output_name) for item in entries]
    title, intro = _timeline_heading(output_name, reference)
    review_html = (_speaker_review_html(speaker_ids, examples)
                   if output_name == DIARIZED_OUTPUT else "")
    session_json = json.dumps(Path(sdir).name, ensure_ascii=False).replace(
        "<", "\\u003c")
    page = f"""<!doctype html>
<html lang="ru"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{title}</title><style>
:root{{color-scheme:dark;--bg:#101417;--card:#182025;--text:#edf3f5;--muted:#9dafb7;--accent:#78d6c6}}
*{{box-sizing:border-box}}html,body{{max-width:100%;overflow-x:hidden}}body{{margin:0;background:var(--bg);color:var(--text);font:17px/1.55 system-ui,sans-serif}}
main{{width:min(980px,calc(100% - 32px));margin:30px auto 110px;overflow-wrap:anywhere}}h1{{font-size:clamp(1.6rem,4vw,2.4rem);overflow-wrap:anywhere}}
.intro,.meta,.no-audio{{color:var(--muted)}}article{{background:var(--card);border:1px solid #2b3940;border-radius:14px;padding:16px 18px;margin:12px 0;scroll-margin-top:90px}}
article{{border-left:5px solid #54656c}}article.speaker-0{{border-left-color:#78d6c6}}article.speaker-1{{border-left-color:#efb366}}article.speaker-2{{border-left-color:#9fa8ff}}article.speaker-3{{border-left-color:#e88db5}}article.speaker-4{{border-left-color:#8ed081}}article.speaker-5{{border-left-color:#df8b76}}article.speaker-6{{border-left-color:#72b6e5}}article.speaker-7{{border-left-color:#cabf70}}
article:target{{border-color:var(--accent);box-shadow:0 0 0 2px #78d6c633}}article p{{white-space:pre-wrap;margin:.5rem 0 1rem}}
a{{color:var(--accent)}}button{{border:1px solid #46615f;border-radius:9px;background:#20302f;color:var(--text);padding:8px 12px;cursor:pointer}}
#speaker-review{{background:#131b1f;border:1px solid #2b3940;border-radius:16px;padding:18px;margin:22px 0}}#speaker-review h2{{margin:.1rem 0 .3rem}}
.speaker-review-guide{{display:grid;grid-template-columns:1fr 1fr;gap:10px;margin:14px 0}}.speaker-review-guide p{{margin:0;padding:12px 14px;border:1px solid #2b3940;border-radius:10px;background:#10171b;color:var(--muted);line-height:1.45}}.speaker-review-guide strong{{display:block;margin-bottom:3px;color:var(--accent)}}
.speaker-row{{--speaker-color:#78d6c6;display:grid;grid-template-columns:minmax(130px,.75fr) minmax(190px,1.35fr) minmax(150px,.9fr) minmax(160px,1fr);gap:12px;align-items:start;border:1px solid #2b3940;border-left:5px solid var(--speaker-color);border-radius:12px;padding:14px;margin:12px 0;background:#10171b;transition:border-color .18s,background .18s,box-shadow .18s}}
.speaker-row.speaker-1{{--speaker-color:#efb366}}.speaker-row.speaker-2{{--speaker-color:#9fa8ff}}.speaker-row.speaker-3{{--speaker-color:#e88db5}}.speaker-row.speaker-4{{--speaker-color:#8ed081}}.speaker-row.speaker-5{{--speaker-color:#df8b76}}.speaker-row.speaker-6{{--speaker-color:#72b6e5}}.speaker-row.speaker-7{{--speaker-color:#cabf70}}
.speaker-row.playing{{border-color:var(--speaker-color);background:#152126;box-shadow:0 0 0 2px color-mix(in srgb,var(--speaker-color) 18%,transparent)}}
.speaker-row label{{display:grid;gap:5px;color:var(--muted);font-size:.82rem}}input,select{{width:100%;min-width:0;border:1px solid #41535b;border-radius:8px;background:#0f1518;color:var(--text);padding:8px 10px;font:inherit}}
.speaker-identity{{display:grid;gap:3px;align-self:start}}.speaker-identity strong{{font-size:1rem;color:var(--text)}}.speaker-identity code{{color:var(--speaker-color);font-size:.72rem}}.speaker-suggestion{{color:var(--muted);font-size:.72rem;line-height:1.3}}.speaker-suggestion.high{{color:#78d6c6}}.speaker-suggestion.review{{color:#efb366}}.apply-suggestion{{justify-self:start;padding:5px 8px;font-size:.72rem}}
.speaker-examples{{grid-column:1/-1;display:grid;grid-template-columns:minmax(145px,.8fr) minmax(260px,2.5fr) auto;gap:10px;align-items:center;border-top:1px solid #2b3940;padding-top:11px;color:var(--muted);font-size:.78rem}}.speaker-example-label{{display:grid;gap:2px}}.speaker-example-label strong{{color:var(--text)}}.speaker-example-label small{{font-size:.68rem}}.speaker-samples{{display:flex;gap:7px;align-items:center;flex-wrap:wrap}}.speaker-examples button{{padding:7px 10px;margin:0;white-space:normal}}.speaker-examples .play-all{{color:var(--speaker-color);border-color:var(--speaker-color)}}.speaker-examples .play.active{{color:#101417;background:var(--speaker-color);border-color:var(--speaker-color)}}
.speaker-bank-actions{{display:flex;align-items:center;gap:12px;flex-wrap:wrap;margin:14px 0}}.bank-consent{{display:flex!important;grid-template-columns:auto 1fr;align-items:flex-start!important;max-width:660px}}.bank-consent input{{width:auto;margin-top:4px}}
.split-speaker{{margin-left:8px;background:#2b2520;border-color:#6a563e}}
.review-actions{{display:flex;align-items:center;gap:12px;margin-top:10px}}button:disabled,input:disabled,select:disabled{{opacity:.55;cursor:not-allowed}}
#dock{{position:fixed;left:0;right:0;bottom:0;background:#111a1eeF;border-top:1px solid #34434a;padding:10px 16px;display:flex;gap:12px;align-items:center}}
#now{{min-width:220px;max-width:38vw;overflow-wrap:anywhere}}#player{{width:min(700px,75vw);min-width:0}}@media(max-width:820px){{.speaker-review-guide{{grid-template-columns:1fr}}.speaker-row{{grid-template-columns:1fr 1fr}}.speaker-examples{{grid-template-columns:1fr}}.speaker-examples .enroll-speaker{{justify-self:start}}}}@media(max-width:600px){{body{{font-size:16px}}main{{margin-top:20px;margin-bottom:82px}}.speaker-row{{grid-template-columns:1fr}}.review-actions{{align-items:stretch;flex-direction:column}}#dock{{padding:6px 10px;gap:4px;flex-direction:column;align-items:stretch}}#now{{min-width:0;max-width:none;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;font-size:.74rem}}#player{{width:100%;height:34px}}}}
</style></head><body><main><h1>{title}</h1>
<p class="intro">{intro}</p>
{review_html}{''.join(cards)}</main><div id="dock"><span id="now">Выберите фрагмент</span><audio id="player" controls preload="metadata"></audio></div>
<script>
const player=document.getElementById('player'), now=document.getElementById('now');
let activeClip=null,clipQueue=[],activeGroup=null;
const clearClip=()=>{{if(activeClip){{activeClip.classList.remove('active');activeClip.setAttribute('aria-pressed','false');activeClip.closest('.speaker-row')?.classList.remove('playing');}}activeClip=null;}};
const finishClip=()=>{{clearClip();if(clipQueue.length){{playClip(clipQueue.shift());return;}}if(activeGroup)activeGroup.classList.remove('active');activeGroup=null;}};
const playClip=button=>{{
  clearClip();activeClip=button;button.classList.add('active');button.setAttribute('aria-pressed','true');button.closest('.speaker-row')?.classList.add('playing');
  const seek=()=>{{player.currentTime=Number(button.dataset.start)||0;player.play().catch(()=>{{}});}};
  const url=new URL(button.dataset.file,location.href).href;
  const article=button.closest('article');
  now.textContent=article?article.querySelector('.meta').textContent.trim():(button.dataset.label||'Аудиопример');
  if(player.src!==url){{player.src=url;player.addEventListener('loadedmetadata',seek,{{once:true}});player.load();}}else{{seek();}}
}};
document.querySelectorAll('.play').forEach(button=>{{button.setAttribute('aria-pressed','false');button.addEventListener('click',()=>{{clipQueue=[];if(activeGroup)activeGroup.classList.remove('active');activeGroup=null;playClip(button);}});}});
document.querySelectorAll('.play-all').forEach(button=>button.addEventListener('click',()=>{{
  clipQueue=[...button.closest('.speaker-row').querySelectorAll('.play.example')];if(!clipQueue.length)return;
  if(activeGroup)activeGroup.classList.remove('active');activeGroup=button;button.classList.add('active');playClip(clipQueue.shift());
}}));
player.addEventListener('timeupdate',()=>{{const end=Number(activeClip?.dataset.end)||0;if(end&&player.currentTime>=end){{player.pause();finishClip();}}}});
player.addEventListener('ended',finishClip);
const review=document.getElementById('speaker-review');
if(review){{
  const sessionName={session_json}, status=document.getElementById('speaker-status');
  const rows=[...document.querySelectorAll('.speaker-row')];let currentSplits=[];
  const endpoint='/api/sessions/'+encodeURIComponent(sessionName)+'/speaker-map';
  const identifyEndpoint='/api/sessions/'+encodeURIComponent(sessionName)+'/speaker-identify';
  const enrollEndpoint='/api/sessions/'+encodeURIComponent(sessionName)+'/speaker-enroll';
  const applyLabels=(speakers,splits=currentSplits)=>{{
    const resolve=(id)=>{{let current=id, seen=new Set();while(speakers[current]&&speakers[current].merge_into&&speakers[current].merge_into!==current&&!seen.has(current)){{seen.add(current);current=speakers[current].merge_into;}}return current;}};
    const effective=(id,start)=>{{const found=splits.filter(item=>item.source===id&&Number(item.start_ms)<=start).sort((a,b)=>Number(b.start_ms)-Number(a.start_ms));return found.length?found[0].speaker_id:id;}};
    document.querySelectorAll('.speaker-label').forEach(label=>{{
      const raw=label.dataset.speaker, effectiveId=effective(raw,Number(label.dataset.start)||0), target=resolve(effectiveId), item=speakers[target]||{{}};
      label.textContent=item.name ? `${{item.name}} (${{effectiveId===target?target:effectiveId+' → '+target}})` : (effectiveId===target?effectiveId:effectiveId+' → '+target);
    }});
  }};
  const loadMap=async()=>{{
    if(location.protocol==='file:'){{status.textContent='Для сохранения откройте страницу из архива Blatero.';rows.forEach(row=>row.querySelectorAll('input,select,button').forEach(field=>field.disabled=true));document.getElementById('save-speakers').disabled=true;document.getElementById('identify-speakers').disabled=true;document.getElementById('speaker-bank-consent').disabled=true;return;}}
    try{{
      const response=await fetch(endpoint,{{cache:'no-store'}});if(!response.ok)throw new Error(await response.text());
      const data=await response.json(), speakers=data.speakers||{{}};currentSplits=data.splits||[];
      rows.forEach(row=>{{const item=speakers[row.dataset.speaker]||{{}};row.querySelector('.speaker-name').value=item.name||'';row.querySelector('.speaker-role').value=item.role||'Собеседник';row.querySelector('.speaker-merge').value=item.merge_into&&item.merge_into!==row.dataset.speaker?item.merge_into:'';}});
      applyLabels(speakers,currentSplits);status.textContent=data.reviewed?'Карта проверена.':'Черновик: назовите все необъединённые кластеры.';if(!location.hash)window.scrollTo(0,0);
    }}catch(error){{status.textContent='Не удалось загрузить карту: '+error.message;}}
  }};
  document.getElementById('save-speakers').addEventListener('click',async()=>{{
    const button=document.getElementById('save-speakers'), speakers={{}};button.disabled=true;status.textContent='Сохраняю…';
    rows.forEach(row=>{{speakers[row.dataset.speaker]={{name:row.querySelector('.speaker-name').value.trim(),role:row.querySelector('.speaker-role').value,merge_into:row.querySelector('.speaker-merge').value||row.dataset.speaker}};}});
    try{{const response=await fetch(endpoint,{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify({{speakers,splits:currentSplits}})}});if(!response.ok)throw new Error(await response.text());const data=await response.json();currentSplits=data.splits||[];applyLabels(data.speakers||{{}},currentSplits);status.textContent=data.reviewed?'Сохранено. Проверенный транскрипт будет использован в отчёте.':'Черновик сохранён. Для отчёта назовите все кластеры, которые не объединены.';}}catch(error){{status.textContent='Не сохранено: '+error.message;}}finally{{button.disabled=false;}}
  }});
  document.getElementById('identify-speakers').addEventListener('click',async()=>{{
    const button=document.getElementById('identify-speakers');button.disabled=true;status.textContent='Сопоставляю локальные голосовые отпечатки…';
    rows.forEach(row=>{{row.querySelector('.apply-suggestion').hidden=true;row.querySelector('.speaker-suggestion').textContent='проверяю…';}});
    try{{
      const response=await fetch(identifyEndpoint,{{method:'POST',headers:{{'Content-Type':'application/json'}},body:'{{}}'}});if(!response.ok)throw new Error(await response.text());
      const data=await response.json(), suggestions=data.suggestions||{{}};
      rows.forEach(row=>{{
        const item=suggestions[row.dataset.speaker]||{{state:'insufficient'}}, label=row.querySelector('.speaker-suggestion'), apply=row.querySelector('.apply-suggestion');
        label.className='speaker-suggestion '+(item.state||'');
        const alternatives=(item.alternatives||[]).slice(0,3).map(value=>value.name+' '+Math.round(Number(value.similarity||0)*100)+'%').join('; ');
        const quality=item.quality||{{}}, rejected=Number(quality.rejected_short||0)+Number(quality.rejected_overlap||0)+Number(quality.rejected_noise||0)+Number(quality.rejected_tts_or_echo||0);
        const details=(item.reason||item.message||'')+(alternatives?' Ближайшие: '+alternatives+'.':'')+(rejected?' Отбраковано фрагментов: '+rejected+'.':'');
        if((item.state==='high'||item.state==='review')&&item.name){{const percent=Math.round(Number(item.similarity||0)*100);label.textContent=(item.state==='high'?'Вероятно: ':'Проверьте: ')+item.name+' · сходство '+percent+'%. '+details;apply.hidden=false;apply.dataset.name=item.name;}}
        else if(item.state==='no_profiles')label.textContent=item.reason||'банк голосов пока пуст';
        else if(item.state==='unknown')label.textContent='Надёжного совпадения нет. '+details;
        else label.textContent=details||'недостаточно чистой речи';
      }});
      status.textContent='Сопоставление готово. Имена не применяются без вашего подтверждения.';
    }}catch(error){{status.textContent='Не удалось сопоставить: '+error.message;}}finally{{button.disabled=false;}}
  }});
  document.querySelectorAll('.apply-suggestion').forEach(button=>button.addEventListener('click',()=>{{
    const row=button.closest('.speaker-row');row.querySelector('.speaker-name').value=button.dataset.name||'';button.hidden=true;status.textContent='Имя подставлено в черновик. Проверьте и сохраните карту голосов.';
  }}));
  document.querySelectorAll('.enroll-speaker').forEach(button=>button.addEventListener('click',async()=>{{
    const row=button.closest('.speaker-row'), name=row.querySelector('.speaker-name').value.trim();
    if(!document.getElementById('speaker-bank-consent').checked){{status.textContent='Для добавления отметьте подтверждение права и согласия.';return;}}
    if(!name){{status.textContent='Сначала укажите имя этого человека.';row.querySelector('.speaker-name').focus();return;}}
    if(!confirm('Создать локальный голосовой отпечаток «'+name+'» из реплик '+row.dataset.speaker+'?'))return;
    button.disabled=true;status.textContent='Создаю локальный голосовой профиль…';
    try{{const response=await fetch(enrollEndpoint,{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify({{speaker_id:row.dataset.speaker,name,consent:true}})}});if(!response.ok)throw new Error(await response.text());const data=await response.json();button.textContent='добавлен: '+data.name;status.textContent='Голосовой профиль создан. Исходное аудио в банк не копировалось.';}}catch(error){{status.textContent='Профиль не создан: '+error.message;button.disabled=false;}}
  }}));
  document.querySelectorAll('.split-speaker').forEach(button=>button.addEventListener('click',async()=>{{
    if(!confirm('Создать новый голос с этой реплики и всех следующих реплик того же кластера?'))return;
    button.disabled=true;status.textContent='Разделяю голос…';
    try{{const response=await fetch('/api/sessions/'+encodeURIComponent(sessionName)+'/speaker-split',{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify({{speaker_id:button.dataset.speaker,start_ms:Number(button.dataset.start)}})}});if(!response.ok)throw new Error(await response.text());location.reload();}}catch(error){{status.textContent='Не разделено: '+error.message;button.disabled=false;}}
  }}));
  loadMap().then(async()=>{{
    if(location.protocol==='file:')return;
    try{{const response=await fetch('/api/speaker-profiles',{{cache:'no-store'}});if(response.ok&&Number((await response.json()).count)>0)document.getElementById('identify-speakers').click();}}catch(_error){{/* Ручная кнопка остаётся доступна. */}}
  }});
}}
</script></body></html>"""
    output = sdir / output_name
    tmp = sdir / f"{output_name}.tmp"
    tmp.write_text(page, encoding="utf-8")
    tmp.replace(output)
    return output, entries


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("session", type=Path)
    parser.add_argument("--reference", action="store_true",
                        help="построить страницу для ручного эталона")
    parser.add_argument("--journal",
                        help="показать конкретный transcript*.jsonl")
    parser.add_argument("--output", help="evidence.html/reference/diarized")
    args = parser.parse_args()
    output, entries = build(
        args.session, reference=args.reference, journal_name=args.journal,
        output_name=args.output)
    if output is None:
        raise SystemExit("Временная шкала не создана: нет реплик JSONL")
    print(f"Временная шкала: {output} ({len(entries)} реплик)")


if __name__ == "__main__":
    main()
