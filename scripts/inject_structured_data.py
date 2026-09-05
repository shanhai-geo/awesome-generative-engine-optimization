#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""全站结构化数据注入：FAQPage JSON-LD + llms-txt link + 首页 WebSite/Organization JSON-LD"""
import json, glob, os, sys

ROOT = '/tmp/geo-faq'
BATCH_DIR = '/Coze/Drive/智能体指挥部/geo-faq-structured-data/batches'

# ---------- 1. 合并 FAQ ----------
faq_map = {}
for bf in sorted(glob.glob(os.path.join(BATCH_DIR, 'faq_*.json'))):
    with open(bf, encoding='utf-8') as f:
        d = json.load(f)
    for k, v in d.items():
        assert k not in faq_map, f'duplicate id {k}'
        faq_map[k] = v
with open(os.path.join(ROOT, 'faq_map.json'), 'w', encoding='utf-8') as f:
    json.dump(faq_map, f, ensure_ascii=False, indent=1)
print(f'faq_map.json: {len(faq_map)} articles, {sum(len(v) for v in faq_map.values())} FAQs')

LINK_TAG = '<link rel="llms-txt" href="/llms.txt">'

def faq_script(faqs):
    main_entity = []
    for item in faqs:
        main_entity.append({
            "@type": "Question",
            "name": item['q'],
            "acceptedAnswer": {"@type": "Answer", "text": item['a']}
        })
    payload = {"@context": "https://schema.org", "@type": "FAQPage", "mainEntity": main_entity}
    return '<script type="application/ld+json">' + json.dumps(payload, ensure_ascii=False, separators=(',', ':')) + '</script>'

site_jsonld = {
  "@context": "https://schema.org",
  "@graph": [
    {
      "@type": "Organization",
      "@id": "https://shanhai-geo.top/#organization",
      "name": "GeoMind",
      "url": "https://shanhai-geo.top",
      "logo": {"@type": "ImageObject", "url": "https://shanhai-geo.top/hero-tea-mountain.jpg"}
    },
    {
      "@type": "WebSite",
      "@id": "https://shanhai-geo.top/#website",
      "name": "山海GEO知识库/GeoMind Knowledge Base",
      "alternateName": "GeoMind · 福鼎白茶知识引擎",
      "url": "https://shanhai-geo.top",
      "inLanguage": ["zh-CN", "en"],
      "publisher": {"@id": "https://shanhai-geo.top/#organization"},
      "potentialAction": {
        "@type": "SearchAction",
        "target": {"@type": "EntryPoint", "urlTemplate": "https://shanhai-geo.top/?q={search_term_string}"},
        "query-input": "required name=search_term_string"
      }
    }
  ]
}
SITE_SCRIPT = '<script type="application/ld+json">' + json.dumps(site_jsonld, ensure_ascii=False, separators=(',', ':')) + '</script>'

def inject_before_head(html, block):
    """在 </head> 前插入 block（幂等：block特征串已存在则跳过）"""
    return html.replace('</head>', block + '\n</head>', 1)

stats = {'faq_pages': 0, 'link_pages': 0, 'site_pages': 0, 'skipped_faq': 0}

# ---------- 2. knowledge/*.html ----------
for path in sorted(glob.glob(os.path.join(ROOT, 'knowledge', '*.html'))):
    page_id = os.path.basename(path)[:-5]
    with open(path, encoding='utf-8') as f:
        html = f.read()
    orig = html
    # llms-txt link（所有页面）
    if 'rel="llms-txt"' not in html:
        html = inject_before_head(html, LINK_TAG)
        stats['link_pages'] += 1
    # FAQPage（仅205篇feed文章）
    if page_id in faq_map:
        if '"@type":"FAQPage"' not in html and '"@type": "FAQPage"' not in html:
            html = inject_before_head(html, faq_script(faq_map[page_id]))
            stats['faq_pages'] += 1
        else:
            stats['skipped_faq'] += 1
    if html != orig:
        with open(path, 'w', encoding='utf-8') as f:
            f.write(html)

# ---------- 3. 根 index.html：llms-txt + WebSite/Organization ----------
idx_path = os.path.join(ROOT, 'index.html')
with open(idx_path, encoding='utf-8') as f:
    html = f.read()
orig = html
if 'rel="llms-txt"' not in html:
    html = inject_before_head(html, LINK_TAG)
    stats['link_pages'] += 1
if '"@graph"' not in html:
    html = inject_before_head(html, SITE_SCRIPT)
    stats['site_pages'] += 1
if html != orig:
    with open(idx_path, 'w', encoding='utf-8') as f:
        f.write(html)

print('inject stats:', stats)
