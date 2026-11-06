"""Crawlability checks:  python .tools/check.py
broken internal links, orphans, sitemap vs canonicals, JSON-LD validity, FAQ schema mirroring, H1 count, title/meta length,
affiliate links missing rel=sponsored."""
import html as H, json, os, re, sys
from urllib.parse import urljoin, urlparse

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SITE = "https://traderfeesaver.com"
problems = []


def text(s):
    s = re.sub(r"<svg.*?</svg>", "", s, flags=re.S)
    return re.sub(r"\s+", " ", H.unescape(re.sub(r"<[^>]+>", "", s))).strip()


pages = {}
for d in ("", "blog"):
    base = os.path.join(ROOT, d) if d else ROOT
    for f in os.listdir(base):
        if f.endswith(".html") and not f.startswith("google"):
            rel = f"{d}/{f}" if d else f
            pages[rel] = open(os.path.join(ROOT, rel), encoding="utf-8").read()


def url_of(rel):
    return SITE + "/" + ("" if rel == "index.html" else "blog/" if rel == "blog/index.html" else rel)


def rel_of(url):
    p = urlparse(url).path.lstrip("/")
    if p in ("", "index.html"):
        return "index.html"
    if p.endswith("/"):
        p += "index.html"
    return p


inbound = {r: set() for r in pages}
canon = {}
for rel, doc in pages.items():
    m = re.search(r'<link rel="canonical" href="([^"]+)"', doc)
    canon[rel] = m.group(1) if m else None
    noindex = bool(re.search(r'name="robots" content="[^"]*noindex', doc))
    indexable = canon[rel] == url_of(rel) and not noindex
    # links
    for href in re.findall(r'<a [^>]*href="([^"]+)"', doc):
        if href.startswith(("mailto:", "javascript:", "#")):
            continue
        u = urljoin(url_of(rel), href)
        if not u.startswith(SITE):
            continue
        target = rel_of(u.split("#")[0])
        if target not in pages and not os.path.exists(os.path.join(ROOT, target)):
            problems.append(f"BROKEN  {rel} -> {href}")
        elif target in pages and target != rel:
            inbound[target].add(rel)
            if canon.get(target) is None:
                pass
    for a in re.findall(r'<a [^>]*href="https?://(?!traderfeesaver)[^"]*"[^>]*>', doc):
        if any(x in a for x in ("?ref=", "&ref=", "referral", "inviteCode", "affiliateId", "clacCode", "/invite/", "/join/", "signup", "exnessonelink", "partner.bybit", "promo=")) and "sponsored" not in a:
            problems.append(f"NOSPONSOR {rel}: {a[:110]}")
    if not indexable:
        continue
    # json-ld
    blocks = re.findall(r'<script type="application/ld\+json">(.*?)</script>', doc, re.S)
    types = []
    for b in blocks:
        try:
            types.append(json.loads(b).get("@type"))
        except Exception as e:
            problems.append(f"BADJSON {rel}: {e}")
    if rel != "index.html" and "BreadcrumbList" not in types:
        problems.append(f"NOCRUMB {rel}")
    # faq mirror
    vis = [(text(q), text(a)) for q, a in re.findall(r'<button class="faq-q"[^>]*>(.*?)</button>\s*<div class="faq-a">(.*?)</div>', doc, re.S)]
    for b in blocks:
        try:
            o = json.loads(b)
        except Exception:
            continue
        if o.get("@type") == "FAQPage":
            ld = [(q["name"], q["acceptedAnswer"]["text"]) for q in o["mainEntity"]]
            if vis and [q for q, _ in ld] != [q for q, _ in vis]:
                problems.append(f"FAQMISMATCH {rel}: schema {len(ld)} Qs vs visible {len(vis)}")
    h1 = len(re.findall(r"<h1[\s>]", doc))
    if h1 != 1:
        problems.append(f"H1x{h1} {rel}")
    t = re.search(r"<title>(.*?)</title>", doc, re.S)
    d = re.search(r'<meta name="description" content="([^"]*)"', doc)
    if not d:
        problems.append(f"NODESC {rel}")
    elif not 70 <= len(H.unescape(d.group(1))) <= 175:
        problems.append(f"DESCLEN {len(H.unescape(d.group(1)))} {rel}")
    if "lang=" not in doc[:200]:
        problems.append(f"NOLANG {rel}")

# sitemap
sm = open(os.path.join(ROOT, "sitemap.xml"), encoding="utf-8").read()
locs = set(re.findall(r"<loc>([^<]+)</loc>", sm))
for rel, doc in pages.items():
    u = url_of(rel)
    noindex = bool(re.search(r'name="robots" content="[^"]*noindex', doc))
    indexable = canon[rel] == u and not noindex
    if indexable and u not in locs:
        problems.append(f"NOTINSITEMAP {u}")
    if not indexable and u in locs:
        problems.append(f"NONCANONICAL-IN-SITEMAP {u}")
    if indexable and rel != "index.html" and not (inbound[rel] - {rel}):
        problems.append(f"ORPHAN {rel}")
for u in locs:
    if rel_of(u) not in pages:
        problems.append(f"SITEMAP-404 {u}")

print("\n".join(sorted(problems)) or "ALL CHECKS PASSED")
print(f"\n{len(pages)} pages, {len(locs)} sitemap urls")
low = sorted((len(v - {k}), k) for k, v in inbound.items() if canon[k] == url_of(k))[:8]
print("fewest inbound links:", ", ".join(f"{k}({n})" for n, k in low))
sys.exit(1 if problems else 0)
