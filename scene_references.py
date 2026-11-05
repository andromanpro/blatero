"""Small reviewed technical references, never facts from a hidden actor profile."""
import re

LOCKS_1C = (
    'Проверенная справка платформы 1С: для управления блокировками в транзакции '
    'используется объект БлокировкаДанных. Он описывает пространства и режимы '
    'блокировок; блокировка устанавливается внутри транзакции. Объектная '
    'блокировка редактирования не заменяет транзакционную защиту данных. '
    'При создании отсутствующей сущности защита нужна по логическому ключу, '
    'а не по ещё отсутствующей ссылке. '
    'Источник: https://v8.1c.ru/platforma/upravlenie-blokirovkami-v-tranzakcii/ '
    'и https://downloads.v8.1c.ru/content/Comm/Platform/8_1_7_37/V8AddDoc81.htm'
)

PERFORMANCE_1C = (
    'Проверенная справка по производительности 1С: замер показывает время и '
    'число исполнений строк, включая серверные вызовы. Частые однотипные запросы '
    'в цикле — одна из возможных причин, не доказанный диагноз без замера. '
    'Групповое получение данных может сократить число обращений; надо сохранить '
    'отборы, права и смысл итогов, сравнить результаты и время на одинаковых данных. '
    'Запросы в цикле не запрещены безусловно: порционная обработка или особенности '
    'виртуальных таблиц могут потребовать другого решения. Не обещать ускорение '
    'добавлением индекса без анализа фактического узкого места. '
    'Источники: https://its.1c.ru/db/content/v8std/src/300/100/i8100436.htm '
    'и https://kb.1ci.com/1C_Enterprise_Platform/1C_Enterprise_Platform_Overview/'
    'Rapid_development_environment/Performance_diagnostics/'
)


def for_question(role, turns):
    if not re.search(r'1[сc]',str(role),re.I):
        return ''
    question=next((str(t.get('text','')) for t in reversed(turns) if t.get('speaker')=='interviewer'),'')
    if re.search(r'блокиров|транзакц|конкурент|одновремен|параллель',question,re.I):
        return LOCKS_1C
    if re.search(r'медлен|ускор|производительн|сорок секунд|тормоз',question,re.I):
        return PERFORMANCE_1C
    return ''
