"""Russian speech aliases. Never rewrite the stored dialogue or report."""
import re

# Version ru2 is part of the immutable scene voice/cache identity.
ALIASES = {
    'WMS': 'вэмээс', '1С': 'один эс', '1C': 'один эс',
    'HTTP': 'эйч ти ти пи', 'HTTPS': 'эйч ти ти пи эс',
    'API': 'эй пи ай', 'REST': 'рэст', 'SOAP': 'соап',
    'JSON': 'джейсон', 'XML': 'икс эм эл', 'SQL': 'эс кью эл',
    'ERP': 'и ар пи', 'CRM': 'си ар эм', 'UUID': 'ю ю ай ди',
    'GUID': 'гуид', 'CPU': 'си пи ю', 'GPU': 'джи пи ю',
    'PDF': 'пи ди эф', 'RTO': 'ар ти о', 'RPO': 'ар пи о',
    'CI/CD': 'си ай си ди', 'UTF-8': 'ю ти эф восемь', 'BPMN': 'би пи эм эн',
    'EDT': 'и ди ти', 'XDTO': 'икс ди ти оу', 'ID': 'ай ди',
    'OLAP': 'олап', 'YAxUnit': 'якс юнит',
}
_LOOKUP = {key.upper(): value for key, value in ALIASES.items()}
_TOKEN = re.compile(r'(?<![\w])(?:' + '|'.join(
    re.escape(key) for key in sorted(ALIASES, key=len, reverse=True)) + r')(?![\w])', re.I)
_URL = re.compile(r'https?://[^\s<>]+', re.I)


def for_speech(text: str) -> str:
    parts, previous = [], 0
    def replace(value):
        return _TOKEN.sub(lambda match: _LOOKUP[match.group().upper()], value)
    for match in _URL.finditer(text):
        parts.extend((replace(text[previous:match.start()]), match.group()))
        previous = match.end()
    parts.append(replace(text[previous:]))
    return ''.join(parts)
