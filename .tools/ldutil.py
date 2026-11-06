"""Replace-or-insert a JSON-LD block by @type, matching on parsed JSON (formatting-independent)."""
import json, re

LD_RE = re.compile(r'[ \t]*<script type="application/ld\+json">(.*?)</script>\n?', re.S)


def upsert(doc, typ, obj):
    block = '  <script type="application/ld+json">' + json.dumps(obj, ensure_ascii=False) + "</script>\n"
    spans = []
    for m in LD_RE.finditer(doc):
        try:
            data = json.loads(m.group(1))
        except Exception:
            continue
        if isinstance(data, dict) and data.get("@type") == typ:
            spans.append((m.start(), m.end()))
    if not spans:
        return doc.replace("</head>", block + "</head>", 1)
    out, last = [], 0
    for i, (a, b) in enumerate(spans):
        out.append(doc[last:a])
        if i == 0:
            out.append(block)
        last = b
    out.append(doc[last:])
    return "".join(out)
