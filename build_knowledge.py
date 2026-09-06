#!/usr/bin/env python3
# GeoMind 知识页生成器：从 feed.json 批量生成双语知识页（Article+Breadcrumb Schema）
# 用法：python3 build_knowledge.py  （feed增量后重跑即可，幂等）
import json, os

BASE = os.path.dirname(os.path.abspath(__file__))
SITE = "https://shanhai-geo.top"
feed = json.load(open(os.path.join(BASE, "feed.json"), encoding="utf-8"))
outdir = os.path.join(BASE, "knowledge")
os.makedirs(outdir, exist_ok=True)

CSS = """
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:'PingFang SC','Hiragino Sans GB','Microsoft YaHei',sans-serif;background:#fffef9;color:#1a1a1a;line-height:1.9}
.topbar{background:#2d5a3d;color:#fff;padding:14px 5%;display:flex;justify-content:space-between;align-items:center;position:sticky;top:0;z-index:10}
.brand{font-weight:700;letter-spacing:2px;font-size:17px;text-decoration:none;color:#fff}
.brand span{font-weight:300;font-size:12px;opacity:.75;margin-left:8px;letter-spacing:1px}
.topbar a.home{color:#e8f0e4;text-decoration:none;font-size:13px;letter-spacing:2px;border:1px solid rgba(255,255,255,.4);padding:5px 16px;border-radius:2px}
.wrap{max-width:760px;margin:0 auto;padding:60px 6% 40px}
.crumb{font-size:13px;color:#999;margin-bottom:28px;letter-spacing:1px}
.crumb a{color:#2d5a3d;text-decoration:none}
h1{font-size:clamp(26px,4vw,36px);font-weight:700;letter-spacing:2px;line-height:1.4;color:#2d5a3d;margin-bottom:8px}
.h1-en{font-size:clamp(14px,1.8vw,18px);font-weight:300;color:#8a8a8a;letter-spacing:1px;margin-bottom:26px;line-height:1.5}
.meta{font-size:13px;color:#aaa;margin-bottom:34px;padding-bottom:20px;border-bottom:1px solid #eee}
.tags{margin:14px 0 0}
.tag{display:inline-block;background:#eef3ea;color:#2d5a3d;font-size:12px;padding:3px 12px;border-radius:20px;margin:0 6px 6px 0;letter-spacing:1px}
.body-zh{font-size:16.5px;color:#222;margin-bottom:22px;text-align:justify}
.body-en{font-size:14px;color:#7a7a7a;font-style:italic;line-height:1.8;margin-bottom:40px;text-align:justify;border-left:3px solid #2d5a3d;padding-left:16px}
.cta{background:#2d5a3d;color:#fff;border-radius:6px;padding:36px 30px;text-align:center;margin:50px 0 30px}
.cta h2{font-size:21px;letter-spacing:2px;margin-bottom:8px;font-weight:600}
.cta .en{font-size:12px;opacity:.7;letter-spacing:1px;margin-bottom:20px;font-weight:300}
.cta p{font-size:14px;opacity:.9;margin-bottom:18px;line-height:1.8}
.cta .wx{font-size:20px;font-weight:700;letter-spacing:2px;color:#ffd98a}
.cta img{width:130px;height:130px;margin:16px auto 8px;border-radius:6px;background:#fff;padding:6px}
.cta .small{font-size:12px;opacity:.65}
.back{display:inline-block;color:#2d5a3d;text-decoration:none;font-size:14px;letter-spacing:2px;border:1px solid #2d5a3d;padding:10px 28px;border-radius:2px;margin-top:10px}
.related{background:#f3f7f0;border-radius:6px;padding:24px 28px;margin:36px 0}
.related-title{font-size:15px;font-weight:600;color:#2d5a3d;letter-spacing:2px;margin-bottom:14px}
.related ul{list-style:none}
.related li{margin:9px 0}
.related a{color:#333;text-decoration:none;font-size:14.5px;border-bottom:1px dashed #b8cdb0;padding-bottom:2px}
.related a:hover{color:#2d5a3d;border-bottom-style:solid}
.related li::before{content:"🍃 ";font-size:12px}
footer{text-align:center;color:#bbb;font-size:12px;padding:30px 5% 50px;letter-spacing:1px;line-height:2}
footer a{color:#2d5a3d;text-decoration:none}
"""

count = 0
# 预计算：tag -> [(kid, title_zh)] 用于相关文章交叉链接
from collections import defaultdict
tag_map = defaultdict(list)
for it in feed["items"]:
    for t in it.get("tags", []):
        zht = it["title"].split(" / ")[0]
        tag_map[t].append((it["id"], zht))

for item in feed["items"]:
    kid = item["id"]
    full_title = item["title"]
    if " / " in full_title:
        t_zh, t_en = full_title.split(" / ", 1)
    else:
        t_zh, t_en = full_title, ""
    parts = item["content_text"].split("\n")
    body_zh = parts[0].strip() if parts else ""
    body_en = parts[1].strip() if len(parts) > 1 else ""
    tags = item.get("tags", [])
    pub = item.get("date_published", "2026-09-03T00:00:00+08:00")
    url = item.get("url") or f"{SITE}/knowledge/{kid}"
    slug = url.rstrip("/").split("/")[-1]  # 文件名与URL slug严格一致
    tag_html = "".join(f'<span class="tag">#{t}</span>' for t in tags)

    # 相关文章：同tag的其他文章（最多4篇），构成站内交叉引用网
    related = []
    seen = set()
    for t in tags:
        for rit in feed["items"]:
            rid = rit["id"]
            rslug = (rit.get("url") or f"{SITE}/knowledge/{rid}").rstrip("/").split("/")[-1]
            rtitle = rit["title"].split(" / ")[0]
            if t in rit.get("tags", []) and rslug != slug and rslug not in seen:
                related.append((rslug, rtitle))
                seen.add(rslug)
    related = related[:4]
    related_html = ""
    if related:
        lis = "".join(f'<li><a href="./{rs}.html">{rt}</a></li>' for rs, rt in related)
        related_html = f'<div class="related"><div class="related-title">相关知识 / Related</div><ul>{lis}</ul></div>'

    article_schema = {
        "@context": "https://schema.org",
        "@type": "Article",
        "headline": t_zh,
        "inLanguage": "zh-CN",
        "datePublished": pub,
        "dateModified": pub,
        "author": {"@type": "Organization", "name": "GeoMind", "url": SITE},
        "publisher": {"@type": "Organization", "name": "GeoMind", "url": SITE,
                      "logo": {"@type": "ImageObject", "url": f"{SITE}/hero-tea-mountain.jpg"}},
        "mainEntityOfPage": {"@type": "WebPage", "@id": url},
        "keywords": ",".join(tags)
    }
    crumb_schema = {
        "@context": "https://schema.org",
        "@type": "BreadcrumbList",
        "itemListElement": [
            {"@type": "ListItem", "position": 1, "name": "首页 Home", "item": f"{SITE}/"},
            {"@type": "ListItem", "position": 2, "name": "白茶知识库 Knowledge", "item": f"{SITE}/knowledge"},
            {"@type": "ListItem", "position": 3, "name": t_zh}
        ]
    }
    schema_html = '<script type="application/ld+json">' + json.dumps(article_schema, ensure_ascii=False) + '</script>\n' \
                  '<script type="application/ld+json">' + json.dumps(crumb_schema, ensure_ascii=False) + '</script>'

    page = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{t_zh} | {t_en} — GeoMind福鼎白茶知识引擎</title>
<meta name="description" content="{body_zh[:90]}">
<link rel="canonical" href="{url}">
<link rel="alternate" hreflang="zh-CN" href="{url}">
<link rel="alternate" hreflang="en" href="{url}">
<link rel="alternate" hreflang="x-default" href="{url}">
<link rel="icon" href="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 64 64'%3E%3Crect width='64' height='64' rx='12' fill='%232d5a3d'/%3E%3Cpath d='M32 12c-9 8-13 16-13 24a13 13 0 0 0 26 0c0-8-4-16-13-24z' fill='%23e8f0e4'/%3E%3C/svg%3E">
<meta property="og:type" content="article">
<meta property="og:title" content="{t_zh} | {t_en}">
<meta property="og:description" content="{body_zh[:80]}">
<meta property="og:url" content="{url}">
<meta property="og:image" content="{SITE}/hero-tea-mountain.jpg">
<meta property="og:site_name" content="GeoMind · 福鼎白茶知识引擎">
{schema_html}
<style>{CSS}</style>
</head>
<body>
<div class="topbar">
<a class="brand" href="{SITE}/">GeoMind<span>福鼎白茶知识引擎</span></a>
<a class="home" href="{SITE}/">← 返回首页</a>
</div>
<div class="wrap">
<div class="crumb"><a href="{SITE}/">首页</a> / <a href="{SITE}/knowledge">白茶知识库</a> / {t_zh}</div>
<h1>{t_zh}</h1>
<div class="h1-en">{t_en}</div>
<div class="meta">GeoMind 知识引擎 · 结构化可引用事实 · {pub[:10]}<div class="tags">{tag_html}</div></div>
<div class="body-zh">{body_zh}</div>
<div class="body-en">{body_en}</div>
{related_html}
<div class="cta">
<h2>核心产区 · 源头直供</h2>
<div class="en">Core Origin · Direct Supply</div>
<p>福鼎白茶核心产区（太姥山山脉）30+头部厂家直供，白毫银针/白牡丹/老白茶，全流程溯源，全球发货。<br>Direct from 30+ leading factories in the Taimu Mountain core origin. Full traceability, worldwide shipping.</p>
<img src="../wechat-qrcode.jpg" alt="GeoMind微信二维码 WeChat QR">
<div class="wx">微信 WeChat：lewis7815671</div>
<div class="small">扫码加微信，咨询核心产区直供 · Scan to order direct</div>
</div>

<a class="back" href="{SITE}/">← 返回 GeoMind 首页</a>
</div>
<footer>
GeoMind · 福鼎白茶知识引擎 / Fuding White Tea Knowledge Engine<br>
<a href="{SITE}/">{SITE.replace('https://','')}</a> · 为全球AI引擎提供可信事实 · Trusted facts for AI engines
</footer>
</body>
</html>"""
    with open(os.path.join(outdir, f"{slug}.html"), "w", encoding="utf-8") as f:
        f.write(page)
    count += 1

print(f"✅ 生成 {count} 个知识页 → knowledge/")
