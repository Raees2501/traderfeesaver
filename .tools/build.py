"""
TraderFeeSaver static builder.

  python .tools/build.py            -> build articles + blog hub + sitemap
  python .tools/build.py sitemap    -> sitemap only

Articles live in .tools/articles/<slug>.src.html with a <!--meta ... --> header,
the body sections, then <!--faq--> (<q>/<a> pairs) and <!--related--> (url | title | desc).
Every article gets: self-canonical, Article + BreadcrumbList + FAQPage JSON-LD generated from
the same text that is rendered on the page (so structured data always mirrors visible content).
"""
import html as H, json, os, re, subprocess, sys, datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SITE = "https://traderfeesaver.com"
TODAY = datetime.date.today().isoformat()
CSS = open(os.path.join(ROOT, ".tools", "article.css"), encoding="utf-8").read().rstrip()
EXTRA_CSS = """
    .toc{background:var(--bg-card);border:1px solid var(--border);border-radius:14px;padding:1.25rem 1.5rem;margin:0 0 3rem}
    .toc-title{font-size:0.75rem;font-weight:700;letter-spacing:0.08em;text-transform:uppercase;color:var(--gold);margin-bottom:0.6rem}
    .toc ol{padding-left:1.2rem;color:var(--muted);font-size:0.9rem;line-height:1.9}
    .toc a{color:var(--muted)}.toc a:hover{color:var(--gold)}
    .article-section h3{font-size:1.08rem;font-weight:700;color:var(--white);margin:1.75rem 0 0.75rem}
    .article-section{scroll-margin-top:80px}
    .quick-answer{background:rgba(14,203,129,0.07);border:1px solid rgba(14,203,129,0.3);border-left:4px solid var(--green);border-radius:12px;padding:1.25rem 1.5rem;margin:0 0 2rem}
    .quick-answer h2{font-size:0.8rem!important;font-weight:800;letter-spacing:0.08em;text-transform:uppercase;color:var(--green);border:none!important;padding:0!important;margin:0 0 0.5rem!important}
    .quick-answer p{color:var(--white)!important;margin:0!important;font-size:0.975rem;line-height:1.75}
    .updated-note{font-size:0.8rem;color:var(--muted);margin-top:0.5rem}
    .faq-item.open .faq-a{max-height:900px}"""

NAV = """  <nav>
    <div class="nav-inner">
      <a href="/" class="nav-logo">TraderFeeSaver</a>
      <div class="nav-links">
        <a href="/">Binance Code</a>
        <a href="/exness.html">Exness Code</a>
        <a href="/prop-firms.html">Prop Firms</a>
        <a href="/blog/" class="active">Blog</a>
      </div>
    </div>
  </nav>"""

CHEVRON = '<svg class="faq-chevron" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="6 9 12 15 18 9"/></svg>'

SCRIPTS = """  <div class="toast" id="toast">&#10003; Copied to clipboard!</div>
  <script>
    function copyCode(code,el){navigator.clipboard.writeText(code).then(()=>{showToast();if(el.classList.contains('code-pill')){el.querySelector('span:last-child').textContent='✓ Copied!';setTimeout(()=>{el.querySelector('span:last-child').textContent='📋 Copy'},2000)}}).catch(()=>{const ta=document.createElement('textarea');ta.value=code;ta.style.position='fixed';ta.style.opacity='0';document.body.appendChild(ta);ta.select();document.execCommand('copy');document.body.removeChild(ta);showToast()})}
    function showToast(){const t=document.getElementById('toast');t.classList.add('show');setTimeout(()=>t.classList.remove('show'),2200)}
    function toggleFaq(btn){const item=btn.closest('.faq-item');const isOpen=item.classList.contains('open');document.querySelectorAll('.faq-item.open').forEach(i=>i.classList.remove('open'));if(!isOpen)item.classList.add('open')}
  </script>
  <script src="/assets/geo-router.js" defer></script>"""


def text(s):
    s = re.sub(r"<[^>]+>", "", s)
    return re.sub(r"\s+", " ", H.unescape(s)).strip()


def attr(s):
    return H.escape(text(s), quote=True)


def ld(obj):
    return '  <script type="application/ld+json">' + json.dumps(obj, ensure_ascii=False) + "</script>"


def human_date(iso):
    d = datetime.date.fromisoformat(iso)
    return d.strftime("%B ") + str(d.day) + d.strftime(", %Y")


def parse(path):
    raw = open(path, encoding="utf-8").read()
    m = re.match(r"\s*<!--meta\n(.*?)\n-->\n(.*)", raw, re.S)
    meta = {}
    for line in m.group(1).splitlines():
        if line.strip():
            k, v = line.split(":", 1)
            meta[k.strip()] = v.strip()
    rest = m.group(2)
    body, _, tail = rest.partition("<!--faq-->")
    faq_raw, _, rel_raw = tail.partition("<!--related-->")
    faqs = re.findall(r"<q>(.*?)</q>\s*<a>(.*?)</a>", faq_raw, re.S)
    related = [tuple(x.strip() for x in l.split("|")) for l in rel_raw.strip().splitlines() if l.strip()]
    return meta, body.strip(), [(q.strip(), a.strip()) for q, a in faqs], related


def build_article(src):
    meta, body, faqs, related = parse(src)
    slug = meta["slug"]
    out_path = meta.get("out", f"blog/{slug}.html")  # root-level pages set out: <file>.html
    meta["_out"] = out_path
    url = f"{SITE}/{out_path}"
    in_blog = out_path.startswith("blog/")
    title, desc = meta["title"], meta["description"]
    full_title = f"{title} | TraderFeeSaver"
    h2s = re.findall(r'<div class="article-section" id="([^"]+)">\s*<h2>(.*?)</h2>', body, re.S)

    toc = ""
    if len(h2s) >= 4:
        toc = '    <div class="toc"><div class="toc-title">In this guide</div><ol>' + "".join(
            f'<li><a href="#{i}">{h}</a></li>' for i, h in h2s) + '<li><a href="#faq">FAQ</a></li></ol></div>\n'
        # quick answer first (snippet candidate), then the contents list
        qa = re.match(r'\s*(<div class="quick-answer">.*?</p>\s*</div>\n)', body, re.S)
        if qa:
            body = body[:qa.end()] + "\n" + toc + body[qa.end():]
            toc = ""

    faq_html = "\n".join(
        f'        <div class="faq-item"><button class="faq-q" onclick="toggleFaq(this)">{q}{CHEVRON}</button><div class="faq-a">{a}</div></div>'
        for q, a in faqs)
    rel_html = "\n".join(
        f'      <a href="{u}" class="internal-link-card"><div class="ilc-label">&#128279; Related Guide</div><h4>{t}</h4><p>{d}</p><span>Read the guide &#8599;</span></a>'
        for u, t, d in related)

    code = meta.get("cta_code", "")
    pill = (f'\n        <div class="code-pill" onclick="copyCode(\'{code}\',this)"><span>{code}</span><span class="copy-icon">&#128203; Copy</span></div>' if code else "")
    box = ""
    if meta.get("box_code"):
        box = f"""    <div class="article-section">
      <div class="big-code-box">
        <div class="bcb-label">{meta['box_label']}</div>
        <div class="bcb-code" onclick="copyCode('{meta['box_code']}',this)">{meta['box_code']}</div>
        <div class="bcb-hint">&#128203; Click to copy</div>
        <a href="{meta['box_url']}" target="_blank" rel="sponsored noopener" class="btn-primary" style="width:100%;justify-content:center;font-size:1rem;">{meta['box_button']} &#8599;</a>
      </div>
    </div>
"""
    published, modified = meta["published"], meta.get("modified", meta["published"])
    date_line = f"&#128197; Published {human_date(published)}" if published == modified else f"&#128197; Updated {human_date(modified)}"

    article_ld = {"@context": "https://schema.org", "@type": "Article", "headline": text(meta.get("headline", title))[:110],
                  "description": text(desc), "datePublished": published, "dateModified": modified, "inLanguage": "en",
                  "author": {"@type": "Organization", "name": "TraderFeeSaver", "url": SITE},
                  "publisher": {"@type": "Organization", "name": "TraderFeeSaver", "url": SITE},
                  "mainEntityOfPage": {"@type": "WebPage", "@id": url}}
    trail = [("Home", SITE + "/")] + ([("Blog", SITE + "/blog/")] if in_blog else []) + [(text(meta["crumb"]), url)]
    crumbs_ld = {"@context": "https://schema.org", "@type": "BreadcrumbList", "itemListElement": [
        {"@type": "ListItem", "position": i + 1, "name": n, "item": u} for i, (n, u) in enumerate(trail)]}
    crumb_mid = '<a href="/blog/">Blog</a><span>&#8250;</span>' if in_blog else ""
    nav = NAV if in_blog else NAV.replace(' class="active"', "")
    faq_ld = {"@context": "https://schema.org", "@type": "FAQPage", "mainEntity": [
        {"@type": "Question", "name": text(q), "acceptedAnswer": {"@type": "Answer", "text": text(a)}} for q, a in faqs]}

    out = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{full_title}</title>
  <meta name="description" content="{attr(desc)}">
  <meta name="robots" content="index, follow, max-image-preview:large, max-snippet:-1">
  <link rel="canonical" href="{url}">
  <meta property="og:type" content="article">
  <meta property="og:site_name" content="TraderFeeSaver">
  <meta property="og:title" content="{attr(full_title)}">
  <meta property="og:description" content="{attr(desc)}">
  <meta property="og:url" content="{url}">
  <meta property="article:published_time" content="{published}">
  <meta property="article:modified_time" content="{modified}">
  <meta name="twitter:card" content="summary">
  <meta name="twitter:title" content="{attr(full_title)}">
  <meta name="twitter:description" content="{attr(desc)}">
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800;900&display=swap" rel="stylesheet">
{ld(article_ld)}
{ld(crumbs_ld)}
{ld(faq_ld)}
  <style>
{CSS}{EXTRA_CSS}
  </style>
</head>
<body>
{nav}
  <div class="breadcrumb">
    <a href="/">Home</a><span>&#8250;</span>{crumb_mid}<span class="current">{meta['crumb']}</span>
  </div>
  <header class="article-hero">
    <div class="article-hero-inner">
      <div class="article-badge">{meta['badge']}</div>
      <h1>{meta['h1']}</h1>
      <div class="article-meta"><span>{date_line}</span><span>&#128336; {meta['read']} min read</span><span>{meta.get('note','')}</span></div>
      <div class="article-cta-row">
        <a href="{meta['cta_url']}" target="_blank" rel="sponsored noopener" class="btn-primary">{meta['cta_label']} &#8599;</a>{pill}
      </div>
    </div>
  </header>
  <main class="article-body">
{toc}
{body}

    <div class="article-section" id="related">
      <h2>Also Worth Reading</h2>
{rel_html}
    </div>

    <div class="article-section" id="faq">
      <h2>Frequently Asked Questions</h2>
      <div class="faq-list">
{faq_html}
      </div>
    </div>

{box}  </main>
  <footer>
    <div class="footer-inner">
      <div class="footer-links"><a href="/">Binance Code</a><a href="/exness.html">Exness Code</a><a href="/prop-firms.html">Prop Firms</a><a href="/blog/">All Guides</a><a href="/fasset-referral-code-2026.html">Fasset Code</a></div>
      <p class="footer-disc">{meta['disclaimer']}</p>
    </div>
  </footer>
{SCRIPTS}
</body>
</html>
"""
    dest = os.path.join(ROOT, *out_path.split("/"))
    open(dest, "w", encoding="utf-8", newline="\n").write(out)
    return slug, meta


# ---------------------------------------------------------------- sitemap
def canonical_of(doc):
    m = re.search(r'<link rel="canonical" href="([^"]+)"', doc)
    return m.group(1) if m else None


def lastmod(rel, doc):
    # Prefer the page's own Article dateModified (content date); fall back to git history.
    m = re.search(r'"dateModified":\s*"(\d{4}-\d{2}-\d{2})"', doc)
    if m:
        return m.group(1)
    dirty = subprocess.run(["git", "status", "--porcelain", "--", rel], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    if dirty:
        return TODAY
    d = subprocess.run(["git", "log", "-1", "--format=%cs", "--", rel], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    return d or TODAY


# ---------------------------------------------------------------- blog hub
HUB_CSS = """
    .hub-hero{padding:2.5rem 1.5rem 2rem;background:radial-gradient(ellipse 70% 50% at 50% 0%,rgba(240,185,11,0.07) 0%,transparent 70%)}
    .hub-hero-inner,.hub-body{max-width:1100px;margin:0 auto}
    .hub-hero h1{font-size:clamp(1.75rem,4vw,2.6rem);font-weight:900;letter-spacing:-0.025em;margin-bottom:0.75rem}
    .hub-hero h1 span{color:var(--gold)}
    .hub-hero p{color:var(--muted);max-width:720px}
    .hub-jump{display:flex;flex-wrap:wrap;gap:0.5rem;margin-top:1.25rem}
    .hub-jump a{font-size:0.8rem;font-weight:600;color:var(--muted);border:1px solid var(--border);border-radius:100px;padding:0.35rem 0.9rem}
    .hub-jump a:hover{color:var(--gold);border-color:rgba(240,185,11,0.4)}
    .hub-body{padding:1rem 1.5rem 5rem}
    .hub-cat{margin:2.5rem 0;scroll-margin-top:80px}
    .hub-cat h2{font-size:1.4rem;font-weight:800;letter-spacing:-0.02em;margin-bottom:0.35rem}
    .hub-cat>p{color:var(--muted);font-size:0.92rem;margin-bottom:1.25rem}
    .blog-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(290px,1fr));gap:1.1rem}
    .blog-card{background:var(--bg-card);border:1px solid var(--border);border-radius:16px;padding:1.6rem;transition:border-color 0.2s,transform 0.2s;display:flex;flex-direction:column;height:100%}
    .blog-card:hover{border-color:rgba(240,185,11,0.5);transform:translateY(-2px)}
    .blog-card-meta{display:flex;align-items:center;gap:0.6rem;margin-bottom:0.85rem;flex-wrap:wrap;font-size:0.78rem;color:var(--muted)}
    .blog-badge{background:rgba(240,185,11,0.12);border:1px solid rgba(240,185,11,0.3);color:var(--gold);font-size:0.7rem;font-weight:700;letter-spacing:0.08em;text-transform:uppercase;padding:0.28rem 0.7rem;border-radius:100px}
    .blog-card h3{font-size:1.02rem;font-weight:800;letter-spacing:-0.01em;margin-bottom:0.5rem;color:var(--white)}
    .blog-card p{font-size:0.86rem;color:var(--muted);line-height:1.65;margin-bottom:1rem;flex:1}
    .blog-card-link{color:var(--gold);font-size:0.85rem;font-weight:700}"""


def build_hub(generated):
    sys.path.insert(0, os.path.join(ROOT, ".tools"))
    import catalog
    pages = list(catalog.PAGES)
    for slug, meta in generated:
        pages.append(("/" + meta["_out"], meta["hub_cat"], meta["hub_badge"], text(meta["title"]).replace(" — ", ": "),
                      meta["hub_desc"], meta.get("modified", meta["published"]), int(meta["read"])))
    sections, items = [], []
    for key, name, blurb in catalog.CATEGORIES:
        rows = sorted([p for p in pages if p[1] == key], key=lambda p: p[5], reverse=True)
        if not rows:
            continue
        cards = "\n".join(
            f'        <a href="{u}"><article class="blog-card"><div class="blog-card-meta"><span class="blog-badge">{b}</span>'
            f'<span>{human_date(d)} &middot; {r} min read</span></div><h3>{t}</h3><p>{ds}</p>'
            f'<span class="blog-card-link">Read the guide &#8599;</span></article></a>'
            for u, _, b, t, ds, d, r in rows)
        sections.append(f'    <section class="hub-cat" id="{key}">\n      <h2>{name}</h2>\n      <p>{blurb}</p>\n'
                        f'      <div class="blog-grid">\n{cards}\n      </div>\n    </section>')
        items += [(t, SITE + u) for u, _, _, t, _, _, _ in rows]
    jump = "".join(f'<a href="#{k}">{n}</a>' for k, n, _ in catalog.CATEGORIES)
    url = SITE + "/blog/"
    title = "Crypto, Forex &amp; Prop Firm Guides 2026 — All Articles | TraderFeeSaver"
    desc = ("Every TraderFeeSaver guide in one place: crypto exchange referral codes, Fasset, Pakistan P2P and card guides, "
            "Exness, and prop firm reviews, updated for 2026.")
    coll = {"@context": "https://schema.org", "@type": "CollectionPage", "name": "TraderFeeSaver Guides", "url": url,
            "description": desc, "inLanguage": "en", "isPartOf": {"@type": "WebSite", "name": "TraderFeeSaver", "url": SITE + "/"},
            "mainEntity": {"@type": "ItemList", "numberOfItems": len(items), "itemListElement": [
                {"@type": "ListItem", "position": i + 1, "url": u, "name": text(t)} for i, (t, u) in enumerate(items)]}}
    crumbs = {"@context": "https://schema.org", "@type": "BreadcrumbList", "itemListElement": [
        {"@type": "ListItem", "position": 1, "name": "Home", "item": SITE + "/"},
        {"@type": "ListItem", "position": 2, "name": "Blog", "item": url}]}
    out = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{title}</title>
  <meta name="description" content="{H.escape(desc, quote=True)}">
  <meta name="robots" content="index, follow, max-image-preview:large, max-snippet:-1">
  <link rel="canonical" href="{url}">
  <meta property="og:type" content="website">
  <meta property="og:site_name" content="TraderFeeSaver">
  <meta property="og:title" content="{title}">
  <meta property="og:description" content="{H.escape(desc, quote=True)}">
  <meta property="og:url" content="{url}">
  <meta name="twitter:card" content="summary">
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800;900&display=swap" rel="stylesheet">
{ld(coll)}
{ld(crumbs)}
  <style>
{CSS}{HUB_CSS}
  </style>
</head>
<body>
{NAV}
  <div class="breadcrumb" style="max-width:1100px">
    <a href="/">Home</a><span>&#8250;</span><span class="current">Blog</span>
  </div>
  <header class="hub-hero">
    <div class="hub-hero-inner">
      <h1>Trading <span>Guides</span> &amp; Referral Codes</h1>
      <p>{len(items)} guides on cutting trading costs: verified exchange sign-up codes, Fasset and crypto cards, buying USDT in Pakistan, Exness, and prop firm challenges. Each one is checked against the platform's own pages and dated, so you know how fresh it is.</p>
      <div class="hub-jump">{jump}</div>
    </div>
  </header>
  <main class="hub-body">
{chr(10).join(sections)}
  </main>
  <footer>
    <div class="footer-inner">
      <div class="footer-links"><a href="/">Binance Code</a><a href="/exness.html">Exness Code</a><a href="/prop-firms.html">Prop Firms</a><a href="/blog/">All Guides</a><a href="/fasset-referral-code-2026.html">Fasset Code</a></div>
      <p class="footer-disc">traderfeesaver.com is an independent affiliate site and may earn a commission when you sign up through our links, at no cost to you. Not financial advice.</p>
    </div>
  </footer>
  <script src="/assets/geo-router.js" defer></script>
</body>
</html>
"""
    open(os.path.join(ROOT, "blog", "index.html"), "w", encoding="utf-8", newline="\n").write(out)
    return len(items)


def build_sitemap():
    entries = []
    for d in ("", "blog"):
        for f in sorted(os.listdir(os.path.join(ROOT, d) if d else ROOT)):
            if not f.endswith(".html") or f.startswith("google"):
                continue
            rel = f"{d}/{f}" if d else f
            doc = open(os.path.join(ROOT, rel), encoding="utf-8").read()
            if re.search(r'<meta name="robots" content="[^"]*noindex', doc, re.I):
                continue
            own = SITE + "/" + ("" if rel == "index.html" else "blog/" if rel == "blog/index.html" else rel)
            if canonical_of(doc) != own:
                continue  # duplicates that canonicalise elsewhere stay out of the sitemap
            entries.append((own, lastmod(rel, doc)))
    entries.sort(key=lambda e: (e[0] != SITE + "/", e[0] != SITE + "/blog/", e[0]))
    xml = ['<?xml version="1.0" encoding="UTF-8"?>', '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
    xml += [f"  <url><loc>{u}</loc><lastmod>{m}</lastmod></url>" for u, m in entries]
    xml.append("</urlset>\n")
    open(os.path.join(ROOT, "sitemap.xml"), "w", encoding="utf-8", newline="\n").write("\n".join(xml))
    return entries


if __name__ == "__main__":
    if len(sys.argv) < 2 or sys.argv[1] != "sitemap":
        srcdir = os.path.join(ROOT, ".tools", "articles")
        generated = []
        for f in sorted(os.listdir(srcdir)):
            if f.endswith(".src.html"):
                generated.append(build_article(os.path.join(srcdir, f)))
                print("built", generated[-1][0])
        print("hub items:", build_hub(generated))
    for u, m in build_sitemap():
        print(m, u)
