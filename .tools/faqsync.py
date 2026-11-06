"""Rebuild a page's FAQPage JSON-LD from its visible .faq-item blocks so structured data always mirrors on-page text."""
import json, os, re, sys, html as H
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ldutil import upsert

def strip(s):
    s = re.sub(r'<svg.*?</svg>', '', s, flags=re.S)
    s = re.sub(r'<[^>]+>', '', s)
    return re.sub(r'\s+', ' ', H.unescape(s)).strip()

def visible_faqs(doc):
    items = re.findall(r'<button class="faq-q"[^>]*>(.*?)</button>\s*<div class="faq-a">(.*?)</div>', doc, flags=re.S)
    return [(strip(q), strip(a)) for q, a in items]

def faq_ld(faqs):
    return json.dumps({"@context": "https://schema.org", "@type": "FAQPage", "mainEntity": [
        {"@type": "Question", "name": q, "acceptedAnswer": {"@type": "Answer", "text": a}} for q, a in faqs]}, ensure_ascii=False)

def sync(path):
    doc = open(path, encoding='utf-8').read()
    faqs = visible_faqs(doc)
    if not faqs:
        return 0
    doc = upsert(doc, 'FAQPage', json.loads(faq_ld(faqs)))
    open(path, 'w', encoding='utf-8', newline='\n').write(doc)
    return len(faqs)

if __name__ == '__main__':
    for p in sys.argv[1:]:
        print(p, sync(p))
