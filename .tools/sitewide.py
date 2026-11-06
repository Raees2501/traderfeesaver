"""
Idempotent sitewide crawlability pass for hand-written pages.

  python .tools/sitewide.py

- "Blog" links (index.html#blog, ../index.html#blog, blog/binance-...) -> /blog/ hub
- adds a Blog item to nav menus that lack one
- BreadcrumbList JSON-LD mirroring the visible breadcrumb (or Home > Page when none is shown)
- WebSite JSON-LD on the homepage
Pages whose canonical points elsewhere (consolidated duplicates) are left alone apart from link fixes.
"""
import html as H, json, os, re
from urllib.parse import urljoin

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SITE = "https://traderfeesaver.com"
SKIP = {"google70ca0e57a0091eb6.html", "blog/bybit-referral-code-2026.html", "blog/index.html"}


def text(s):
    return re.sub(r"\s+", " ", H.unescape(re.sub(r"<[^>]+>", "", s))).strip()


def own_url(rel):
    return SITE + "/" + ("" if rel == "index.html" else rel)


def abs_href(rel, href):
    if href.endswith("#blog") or href in ("/blog/", "blog/", "../blog/"):
        return SITE + "/blog/"
    u = urljoin(own_url(rel), href.split("#")[0])
    return SITE + "/" if u in (SITE + "/index.html", SITE + "/index.html/") else u


def crumbs_for(rel, doc):
    m = re.search(r'<div class="breadcrumb">(.*?)</div>', doc, re.S)
    items = []
    if m:
        for href, label in re.findall(r'<a href="([^"]+)"[^>]*>(.*?)</a>', m.group(1), re.S):
            items.append((text(label), abs_href(rel, href)))
        cur = re.search(r'<span class="current">(.*?)</span>', m.group(1), re.S)
        if cur:
            items.append((text(cur.group(1)), own_url(rel)))
    if not items:
        t = re.search(r"<title>(.*?)</title>", doc, re.S)
        name = re.split(r" [-—|] ", text(t.group(1)))[0] if t else rel
        items = [("Home", SITE + "/"), (name, own_url(rel))]
    if items and items[0][1] != SITE + "/":
        items.insert(0, ("Home", SITE + "/"))
    items[-1] = (items[-1][0], own_url(rel))
    return items


import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ldutil import upsert as upsert_ld


def process(rel):
    path = os.path.join(ROOT, rel)
    doc = orig = open(path, encoding="utf-8").read()

    # 1. Blog links -> hub
    doc = re.sub(r'href="(?:\.\./)?index\.html#blog"', 'href="/blog/"', doc)
    doc = doc.replace('<a href="blog/binance-referral-code-2026.html">Blog</a>', '<a href="/blog/">Blog</a>')
    doc = doc.replace('<a href="../index.html#blog" class="active">Blog</a>', '<a href="/blog/" class="active">Blog</a>')

    # 1b. homepage links -> "/" (index.html is only an alternate of / and wastes crawls)
    doc = re.sub(r'href="(?:\.\./)?index\.html(#[^"]*)?"', lambda m: 'href="/' + (m.group(1) or "") + '"', doc)

    # 1c. footer link to the Fasset money page on every page
    def add_fasset(m):
        if "fasset-referral-code-2026.html" in m.group(0):
            return m.group(0)
        return m.group(0)[:-len("</div>")] + '<a href="/fasset-referral-code-2026.html">Fasset Code</a></div>'
    doc = re.sub(r'<div class="footer-links">.*?</div>', add_fasset, doc, count=1, flags=re.S)

    # 2. nav Blog item (simple nav-links blocks without nested divs)
    def add_blog(m):
        inner = m.group(2)
        if "/blog/" in inner or ">Blog<" in inner or "<div" in inner:
            return m.group(0)
        return m.group(1) + inner + '\n        <a href="/blog/">Blog</a>' + m.group(3)
    doc = re.sub(r'(<div class="nav-links">)(.*?)(\n\s*</div>)', add_blog, doc, count=1, flags=re.S)

    canon = re.search(r'<link rel="canonical" href="([^"]+)"', doc)
    if canon and canon.group(1) == own_url(rel):
        if rel == "index.html":
            doc = upsert_ld(doc, "WebSite", {"@context": "https://schema.org", "@type": "WebSite", "name": "TraderFeeSaver",
                                             "alternateName": "Trader Fee Saver", "url": SITE + "/"})
        else:
            items = crumbs_for(rel, doc)
            doc = upsert_ld(doc, "BreadcrumbList", {"@context": "https://schema.org", "@type": "BreadcrumbList", "itemListElement": [
                {"@type": "ListItem", "position": i + 1, "name": n, "item": u} for i, (n, u) in enumerate(items)]})

    if doc != orig:
        open(path, "w", encoding="utf-8", newline="\n").write(doc)
        return True
    return False


if __name__ == "__main__":
    for d in ("", "blog"):
        base = os.path.join(ROOT, d) if d else ROOT
        for f in sorted(os.listdir(base)):
            rel = f"{d}/{f}" if d else f
            if f.endswith(".html") and rel not in SKIP:
                if process(rel):
                    print("updated", rel)
