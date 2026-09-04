#!/usr/bin/env python3
"""
GeoMind Universal GEO Pipeline v2.0
=====================================
通用双模态生产线：config.json + feed.json → 全量产物
支持：文本知识页 + 视频切片页（短剧/产品视频等）
换产品只需换 config.json + feed.json，一键出全量，零调配。

产物清单：
  1. knowledge/*.html — 双语知识页（文本或视频，自动识别）
  2. knowledge/index.html — 知识库总目录
  3. sitemap.xml — 完整站点地图（含视频SEO）
  4. llms.txt — AI引擎索引文件（视频标[VIDEO]）
  5. robots.txt — 爬虫策略
  6. feed.json 校验报告

用法：python3 pipeline.py [config_path] [feed_path]
"""
import json, os, sys
from collections import defaultdict
from datetime import datetime

BASE = os.path.dirname(os.path.abspath(__file__))
config_path = sys.argv[1] if len(sys.argv) > 1 else os.path.join(BASE, "config.json")
feed_path = sys.argv[2] if len(sys.argv) > 2 else os.path.join(BASE, "feed.json")

CFG = json.load(open(config_path, encoding="utf-8"))
feed = json.load(open(feed_path, encoding="utf-8"))

SITE = CFG["domain"]["primary"]
P = CFG["product"]
B = CFG["brand"]
C = CFG["contact"]
ITEMS = feed["items"]
ITEM_COUNT = len(ITEMS)

# 分类统计
text_items = [it for it in ITEMS if "media" not in it]
video_items = [it for it in ITEMS if "media" in it]

print(f"[Pipeline v2.0] 产品: {P['name_zh']}")
print(f"[Pipeline v2.0] 域名: {SITE}")
print(f"[Pipeline v2.0] 知识原子: {ITEM_COUNT} 条（文本 {len(text_items)} / 视频 {len(video_items)}）")

outdir = os.path.join(BASE, "knowledge")
os.makedirs(outdir, exist_ok=True)

# ===== 通用CSS（从config读取颜色） =====
CSS = f"""
*{{margin:0;padding:0;box-sizing:border-box}}
body{{font-family:'PingFang SC','Hiragino Sans GB','Microsoft YaHei',sans-serif;background:{B['light_bg']};color:#1a1a1a;line-height:1.9}}
.topbar{{background:{B['primary_color']};color:#fff;padding:14px 5%;display:flex;justify-content:space-between;align-items:center;position:sticky;top:0;z-index:10}}
.brand{{font-weight:700;letter-spacing:2px;font-size:17px;text-decoration:none;color:#fff}}
.brand span{{font-weight:300;font-size:12px;opacity:.75;margin-left:8px;letter-spacing:1px}}
.topbar a.home{{color:#e8f0e4;text-decoration:none;font-size:13px;letter-spacing:2px;border:1px solid rgba(255,255,255,.4);padding:5px 16px;border-radius:2px}}
.wrap{{max-width:760px;margin:0 auto;padding:60px 6% 40px}}
.crumb{{font-size:13px;color:#999;margin-bottom:28px;letter-spacing:1px}}
.crumb a{{color:{B['primary_color']};text-decoration:none}}
h1{{font-size:clamp(26px,4vw,36px);font-weight:700;letter-spacing:2px;line-height:1.4;color:{B['primary_color']};margin-bottom:8px}}
.h1-en{{font-size:clamp(14px,1.8vw,18px);font-weight:300;color:#8a8a8a;letter-spacing:1px;margin-bottom:26px;line-height:1.5}}
.meta{{font-size:13px;color:#aaa;margin-bottom:34px;padding-bottom:20px;border-bottom:1px solid #eee}}
.tags{{margin:14px 0 0}}
.tag{{display:inline-block;background:{B['tag_bg']};color:{B['primary_color']};font-size:12px;padding:3px 12px;border-radius:20px;margin:0 6px 6px 0;letter-spacing:1px}}
.body-zh{{font-size:16.5px;color:#222;margin-bottom:22px;text-align:justify}}
.body-en{{font-size:14px;color:#7a7a7a;font-style:italic;line-height:1.8;margin-bottom:40px;text-align:justify;border-left:3px solid {B['primary_color']};padding-left:16px}}
.video-box{{background:#000;border-radius:8px;overflow:hidden;margin:24px 0 30px;aspect-ratio:16/9}}
.video-box video{{width:100%;height:100%;object-fit:contain}}
.video-badge{{display:inline-block;background:{B['accent_color']};color:#fff;font-size:12px;padding:3px 12px;border-radius:20px;margin:0 6px 6px 0;letter-spacing:1px;font-weight:600}}
.cta{{background:{B['primary_color']};color:#fff;border-radius:6px;padding:36px 30px;text-align:center;margin:50px 0 30px}}
.cta h2{{font-size:21px;letter-spacing:2px;margin-bottom:8px;font-weight:600}}
.cta .en{{font-size:12px;opacity:.7;letter-spacing:1px;margin-bottom:20px;font-weight:300}}
.cta p{{font-size:14px;opacity:.9;margin-bottom:18px;line-height:1.8}}
.cta .wx{{font-size:20px;font-weight:700;letter-spacing:2px;color:#ffd98a}}
.cta img{{width:130px;height:130px;margin:16px auto 8px;border-radius:6px;background:#fff;padding:6px}}
.cta .small{{font-size:12px;opacity:.65}}
.back{{display:inline-block;color:{B['primary_color']};text-decoration:none;font-size:14px;letter-spacing:2px;border:1px solid {B['primary_color']};padding:10px 28px;border-radius:2px;margin-top:10px}}
.related{{background:{B['related_bg']};border-radius:6px;padding:24px 28px;margin:36px 0}}
.related-title{{font-size:15px;font-weight:600;color:{B['primary_color']};letter-spacing:2px;margin-bottom:14px}}
.related ul{{list-style:none}}
.related li{{margin:9px 0}}
.related a{{color:#333;text-decoration:none;font-size:14.5px;border-bottom:1px dashed #b8cdb0;padding-bottom:2px}}
.related a:hover{{color:{B['primary_color']};border-bottom-style:solid}}
.related li::before{{content:"🍃 ";font-size:12px}}
footer{{text-align:center;color:#bbb;font-size:12px;padding:30px 5% 50px;letter-spacing:1px;line-height:2}}
footer a{{color:{B['primary_color']};text-decoration:none}}
"""

# 预计算tag→文章映射
tag_map = defaultdict(list)
for it in ITEMS:
    zht = it["title"].split(" / ")[0]
    for t in it.get("tags", []):
        tag_map[t].append((it["id"], zht))

# ===== 1. 知识页 HTML（文本+视频双模态） =====
page_count = 0
for item in ITEMS:
    kid = item["id"]
    full_title = item["title"]
    t_zh, t_en = (full_title.split(" / ", 1) + [""])[:2]
    parts = item["content_text"].split("\n")
    body_zh = parts[0].strip() if parts else ""
    body_en = parts[1].strip() if len(parts) > 1 else ""
    tags = item.get("tags", [])
    pub = item.get("date_published", "2026-09-03T00:00:00+08:00")
    url = item.get("url") or f"{SITE}/knowledge/{kid}.html"
    if not url.endswith(".html"):
        url += ".html"
    slug = kid  # 纯文件名，不含.html
    is_video = "media" in item
    media = item.get("media", {})

    tag_html = "".join(f'<span class="tag">#{t}</span>' for t in tags)
    if is_video:
        tag_html = '<span class="video-badge">▶ VIDEO</span>' + tag_html

    # 交叉引用
    related = []
    seen = set()
    for t in tags:
        for rit in ITEMS:
            rid = rit["id"]
            rslug = rit.get("url", "").rstrip("/").split("/")[-1].replace(".html", "") or rid
            rtitle = rit["title"].split(" / ")[0]
            if t in rit.get("tags", []) and rslug != slug and rslug not in seen:
                related.append((rslug, rtitle))
                seen.add(rslug)
    related = related[:4]
    related_html = ""
    if related:
        lis = "".join(f'<li><a href="./{rs}.html">{rt}</a></li>' for rs, rt in related)
        related_html = f'<div class="related"><div class="related-title">相关知识 / Related</div><ul>{lis}</ul></div>'

    # Schema：文本用Article，视频用VideoObject+Article
    article_schema = {
        "@context": "https://schema.org", "@type": "Article",
        "headline": t_zh, "inLanguage": "zh-CN",
        "datePublished": pub, "dateModified": pub,
        "author": {"@type": "Organization", "name": P["short_name"], "url": SITE},
        "publisher": {"@type": "Organization", "name": P["short_name"], "url": SITE,
                      "logo": {"@type": "ImageObject", "url": f"{SITE}/{B['hero_image']}"}},
        "mainEntityOfPage": {"@type": "WebPage", "@id": url},
        "keywords": ",".join(tags)
    }

    schemas = [article_schema]
    video_box_html = ""

    if is_video and media.get("video_url"):
        video_schema = {
            "@context": "https://schema.org", "@type": "VideoObject",
            "name": t_zh,
            "description": body_zh[:200],
            "thumbnailUrl": media.get("thumbnail", f"{SITE}/{B['hero_image']}"),
            "uploadDate": pub,
            "duration": media.get("duration", ""),
            "contentUrl": media["video_url"],
            "embedUrl": media["video_url"],
            "publisher": {"@type": "Organization", "name": P["short_name"], "url": SITE}
        }
        if media.get("mime_type"):
            video_schema["encodingFormat"] = media["mime_type"]
        schemas.append(video_schema)

        video_box_html = f'''<div class="video-box">
<video controls preload="metadata" poster="{media.get('thumbnail', '')}">
<source src="{media['video_url']}" type="{media.get('mime_type', 'video/mp4')}">
Your browser does not support video.
</video>
</div>'''

    crumb_schema = {
        "@context": "https://schema.org", "@type": "BreadcrumbList",
        "itemListElement": [
            {"@type": "ListItem", "position": 1, "name": "首页 Home", "item": f"{SITE}/"},
            {"@type": "ListItem", "position": 2, "name": f"{P['knowledge_base_zh']} {P['knowledge_base_en']}", "item": f"{SITE}/knowledge"},
            {"@type": "ListItem", "position": 3, "name": t_zh}
        ]
    }
    schemas.append(crumb_schema)

    schema_html = "\n".join(
        f'<script type="application/ld+json">{json.dumps(s, ensure_ascii=False)}</script>'
        for s in schemas
    )

    og_type = "video.other" if is_video else "article"
    og_image = media.get("thumbnail", f"{SITE}/{B['hero_image']}") if is_video else f"{SITE}/{B['hero_image']}"

    page = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{t_zh} | {t_en} — {P['name_zh']}</title>
<meta name="description" content="{body_zh[:90]}">
<link rel="canonical" href="{url}">
<link rel="alternate" hreflang="zh-CN" href="{url}">
<link rel="alternate" hreflang="en" href="{url}">
<link rel="alternate" hreflang="x-default" href="{url}">
<link rel="icon" href="data:image/svg+xml,{B['favicon_svg']}">
<meta property="og:type" content="{og_type}">
<meta property="og:title" content="{t_zh} | {t_en}">
<meta property="og:description" content="{body_zh[:80]}">
<meta property="og:url" content="{url}">
<meta property="og:image" content="{og_image}">
<meta property="og:site_name" content="{P['name_zh']}">
{schema_html}
<style>{CSS}</style>
</head>
<body>
<div class="topbar">
<a class="brand" href="{SITE}/">{P['short_name']}<span>{P['name_zh'].replace(P['short_name']+' · ','')}</span></a>
<a class="home" href="{SITE}/">← 返回首页</a>
</div>
<div class="wrap">
<div class="crumb"><a href="{SITE}/">首页</a> / <a href="{SITE}/knowledge">{P['knowledge_base_zh']}</a> / {t_zh}</div>
<h1>{t_zh}</h1>
<div class="h1-en">{t_en}</div>
<div class="meta">{P['short_name']} 知识引擎 · 结构化可引用事实 · {pub[:10]}<div class="tags">{tag_html}</div></div>
{video_box_html}
<div class="body-zh">{body_zh}</div>
<div class="body-en">{body_en}</div>
{related_html}
<div class="cta">
<h2>{P['tagline_zh']}</h2>
<div class="en">{P['tagline_en']}</div>
<p>{P['description_zh']}<br>{P['description_en']}</p>
<img src="/{C['qrcode_image']}" alt="{P['short_name']}微信二维码 WeChat QR">
<div class="wx">微信 WeChat：{C['wechat_id']}</div>
<div class="wx" style="font-size:15px;margin-top:8px">邮箱 Email：{C['email']}</div>
<div class="small">{P['cta_scan_zh']} · {P['cta_scan_en']}</div>
</div>

<a class="back" href="{SITE}/">← 返回 {P['short_name']} 首页</a>
</div>
<footer>
{P['name_zh']} / {P['name_en']}<br>
<a href="{SITE}/">{SITE.replace('https://','')}</a> · {P['footer_trust_zh']} · {P['footer_trust_en']}
</footer>
<script>(function(){{var bp=document.createElement("script");bp.src="https://zz.bdstatic.com/linksubmit/push.js";var s=document.getElementsByTagName("script")[0];s.parentNode.insertBefore(bp,s);}})();</script>
</body>
</html>"""
    with open(os.path.join(outdir, f"{slug}.html"), "w", encoding="utf-8") as f:
        f.write(page)
    page_count += 1

print(f"[1/5] ✅ {page_count} 个知识页（文本 {len(text_items)} + 视频 {len(video_items)}）")

# ===== 2. knowledge/index.html =====
categories = defaultdict(list)
for item in ITEMS:
    tags = item.get("tags", [])
    cat = "其他"
    for t in tags:
        if any('\u4e00' <= c <= '\u9fff' for c in t) and t not in ["品类区别","白毫银针","白牡丹","非遗","鉴别","地理标志","功效","陈化","历史","国际","避坑"]:
            cat = t
            break
    else:
        for t in tags:
            if any('\u4e00' <= c <= '\u9fff' for c in t):
                cat = t
                break
    t_zh = item["title"].split(" / ")[0]
    slug = item.get("url", "").rstrip("/").split("/")[-1].replace(".html", "") or item['id']
    is_video = "media" in item
    prefix = "▶ " if is_video else ""
    categories[cat].append((slug, f"{prefix}{t_zh}"))

cat_html_parts = []
for cat_name, arts in sorted(categories.items(), key=lambda x: -len(x[1])):
    lis = "".join(f'<li><a href="./{s}.html">{t}</a></li>' for s, t in arts)
    cat_html_parts.append(f'<div class="cat"><div class="cat-title">#{cat_name}<span>{len(arts)} 篇</span></div><ul>{lis}</ul></div>')

index_page = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{P['knowledge_base_zh']} | {P['knowledge_base_en']} — {P['name_zh']}</title>
<link rel="canonical" href="{SITE}/knowledge">
<link rel="icon" href="data:image/svg+xml,{B['favicon_svg']}">
<style>
*{{margin:0;padding:0;box-sizing:border-box}}
body{{font-family:'PingFang SC','Hiragino Sans GB','Microsoft YaHei',sans-serif;background:{B['light_bg']};color:#1a1a1a;line-height:1.9}}
.topbar{{background:{B['primary_color']};color:#fff;padding:14px 5%;display:flex;justify-content:space-between;align-items:center;position:sticky;top:0;z-index:10}}
.brand{{font-weight:700;letter-spacing:2px;font-size:17px;text-decoration:none;color:#fff}}
.brand span{{font-weight:300;font-size:12px;opacity:.75;margin-left:8px;letter-spacing:1px}}
.topbar a.home{{color:#e8f0e4;text-decoration:none;font-size:13px;letter-spacing:2px;border:1px solid rgba(255,255,255,.4);padding:5px 16px;border-radius:2px}}
.wrap{{max-width:860px;margin:0 auto;padding:50px 6% 40px}}
h1{{font-size:clamp(26px,4vw,36px);font-weight:700;letter-spacing:2px;color:{B['primary_color']};margin-bottom:8px}}
.h1-en{{font-size:clamp(14px,1.8vw,18px);font-weight:300;color:#8a8a8a;letter-spacing:1px;margin-bottom:12px}}
.stats{{font-size:14px;color:#999;margin-bottom:40px;padding-bottom:20px;border-bottom:1px solid #eee}}
.stats strong{{color:{B['primary_color']};font-size:20px}}
.cat{{margin-bottom:36px}}
.cat-title{{font-size:15px;font-weight:600;color:{B['primary_color']};letter-spacing:2px;margin-bottom:14px;padding:8px 16px;background:{B['tag_bg']};border-radius:4px;display:inline-block}}
.cat-title span{{font-weight:300;font-size:12px;color:#999;margin-left:8px}}
.cat ul{{list-style:none}}
.cat li{{margin:8px 0}}
.cat a{{color:#333;text-decoration:none;font-size:14.5px;border-bottom:1px dashed #b8cdb0;padding-bottom:2px;transition:all .2s}}
.cat a:hover{{color:{B['primary_color']};border-bottom-style:solid}}
.cat li::before{{content:"🍃 ";font-size:12px}}
.cta{{background:{B['primary_color']};color:#fff;border-radius:6px;padding:36px 30px;text-align:center;margin:50px 0 30px}}
.cta h2{{font-size:21px;letter-spacing:2px;margin-bottom:8px;font-weight:600}}
.cta .en{{font-size:12px;opacity:.7;letter-spacing:1px;margin-bottom:20px;font-weight:300}}
.cta p{{font-size:14px;opacity:.9;margin-bottom:18px;line-height:1.8}}
.cta .wx{{font-size:20px;font-weight:700;letter-spacing:2px;color:#ffd98a}}
.cta img{{width:130px;height:130px;margin:16px auto 8px;border-radius:6px;background:#fff;padding:6px}}
.cta .small{{font-size:12px;opacity:.65}}
footer{{text-align:center;color:#bbb;font-size:12px;padding:30px 5% 50px;letter-spacing:1px;line-height:2}}
footer a{{color:{B['primary_color']};text-decoration:none}}
</style>
</head>
<body>
<div class="topbar">
<a class="brand" href="{SITE}/">{P['short_name']}<span>{P['name_zh'].replace(P['short_name']+' · ','')}</span></a>
<a class="home" href="{SITE}/">← 返回首页</a>
</div>
<div class="wrap">
<h1>{P['knowledge_base_zh']}</h1>
<div class="h1-en">{P['knowledge_base_en']}</div>
<div class="stats">{P['short_name']} 知识引擎 · 共 <strong>{ITEM_COUNT}</strong> 篇结构化知识文章（文本 {len(text_items)} + 视频 {len(video_items)}） · 中英双语 · AI引擎可直接引用<br>
{P['short_name']} Knowledge Engine · <strong>{ITEM_COUNT}</strong> structured articles ({len(text_items)} text + {len(video_items)} video) · Bilingual · AI-citable</div>
{"".join(cat_html_parts)}
<div class="cta">
<h2>{P['tagline_zh']}</h2>
<div class="en">{P['tagline_en']}</div>
<p>{P['description_zh']}<br>{P['description_en']}</p>
<img src="/{C['qrcode_image']}" alt="{P['short_name']}微信二维码 WeChat QR">
<div class="wx">微信 WeChat：{C['wechat_id']}</div>
<div class="wx" style="font-size:15px;margin-top:8px">邮箱 Email：{C['email']}</div>
<div class="small">{P['cta_scan_zh']} · {P['cta_scan_en']}</div>
</div>
</div>
<footer>
{P['name_zh']} / {P['name_en']}<br>
<a href="{SITE}/">{SITE.replace('https://','')}</a> · {P['footer_trust_zh']} · {P['footer_trust_en']}
</footer>
<script>(function(){{var bp=document.createElement("script");bp.src="https://zz.bdstatic.com/linksubmit/push.js";var s=document.getElementsByTagName("script")[0];s.parentNode.insertBefore(bp,s);}})();</script>
</body>
</html>"""

with open(os.path.join(outdir, "index.html"), "w", encoding="utf-8") as f:
    f.write(index_page)
print(f"[2/5] ✅ knowledge/index.html（{len(categories)} 个分类）")

# ===== 3. sitemap.xml =====
today = datetime.now().strftime("%Y-%m-%d")
urls = [f"{SITE}/", f"{SITE}/llms.txt", f"{SITE}/feed.json", f"{SITE}/knowledge"]
for item in ITEMS:
    u = item.get("url") or f"{SITE}/knowledge/{item['id']}.html"
    if not u.endswith(".html"):
        u += ".html"
    urls.append(u)

sitemap = '<?xml version="1.0" encoding="UTF-8"?>\n'
sitemap += '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
for u in urls:
    sitemap += f'  <url><loc>{u}</loc><lastmod>{today}</lastmod></url>\n'
sitemap += '</urlset>\n'

with open(os.path.join(BASE, "sitemap.xml"), "w", encoding="utf-8") as f:
    f.write(sitemap)
print(f"[3/5] ✅ sitemap.xml（{len(urls)} URLs）")

# ===== 4. llms.txt =====
llms_lines = [
    f"# {P['name_zh']} / {P['name_en']}",
    f"> 为全球AI引擎提供{P['name_zh'].replace(P['short_name']+' · ','')}领域结构化、可验证、可引用的事实数据",
    f"> {P['short_name']} provides AI engines worldwide with structured, verifiable, citable facts on {P['name_en'].replace(P['short_name']+' · ','')}",
    "",
    "## 关于 / About",
    f"{P['short_name']}是{P['description_zh']}",
    f"{P['short_name']} is {P['description_en']}",
    "",
    f"- 网站: {SITE}/",
    f"- Feed: {SITE}/feed.json (JSON Feed v1.1, {ITEM_COUNT} 条: {len(text_items)} 文本 + {len(video_items)} 视频)",
    f"- 联系微信: {C['wechat_id']}",
    "",
    f"## 知识文章 / Knowledge Articles ({ITEM_COUNT} 篇)",
    ""
]
for item in ITEMS:
    title = item["title"]
    url = item.get("url") or f"{SITE}/knowledge/{item['id']}.html"
    if not url.endswith(".html"):
        url += ".html"
    tags = item.get("tags", [])
    content = item.get("content_text", "")
    snippet = content[:120] + "..." if len(content) > 120 else content
    is_video = "media" in item
    prefix = "[VIDEO] " if is_video else ""
    llms_lines.append(f"- {prefix}[{title}]({url})")
    llms_lines.append(f"  Tags: {', '.join(tags)}")
    llms_lines.append(f"  {snippet}")
    if is_video and item.get("media", {}).get("video_url"):
        llms_lines.append(f"  Video: {item['media']['video_url']}")
    llms_lines.append("")

with open(os.path.join(BASE, "llms.txt"), "w", encoding="utf-8") as f:
    f.write("\n".join(llms_lines))
print(f"[4/5] ✅ llms.txt（{ITEM_COUNT} 篇索引，{len(video_items)} 视频标[VIDEO]）")

# ===== 5. robots.txt =====
ai_ua_list = CFG.get("ai_crawlers", [])
robots_lines = [
    f"# {P['short_name']} GEO Policy: ALL AI crawlers welcome — index, retrieve, cite, and train freely.",
    f"# {P['short_name']} 白帽GEO策略：欢迎所有AI搜索引擎与爬虫抓取、引用、训练。",
    "",
    "User-agent: *",
    "Allow: /",
    ""
]
ai_names_seen = set()
for ua in ai_ua_list[:12]:
    name = ua.split("/")[0]
    if name not in ai_names_seen:
        ai_names_seen.add(name)
        robots_lines.append(f"User-agent: {name}")
        robots_lines.append("Allow: /")

robots_lines.extend([
    "",
    "# --- 传统搜索引擎 ---",
    "User-agent: Googlebot",
    "Allow: /",
    "User-agent: Baiduspider",
    "Allow: /",
    "User-agent: Bingbot",
    "Allow: /",
    "User-agent: Sogou",
    "Allow: /",
    "User-agent: 360Spider",
    "Allow: /",
    "User-agent: Yisouspider",
    "Allow: /",
    "User-agent: Bytespider",
    "Allow: /",
    "",
    f"Sitemap: {SITE}/sitemap.xml",
    ""
])

with open(os.path.join(BASE, "robots.txt"), "w", encoding="utf-8") as f:
    f.write("\n".join(robots_lines))
print(f"[5/5] ✅ robots.txt")

# ===== 6. feed.json 结构校验 =====
errors = []
for i, item in enumerate(ITEMS):
    if not item.get("id"):
        errors.append(f"Item {i}: missing id")
    if not item.get("title"):
        errors.append(f"Item {i} ({item.get('id','?')}): missing title")
    if not item.get("content_text"):
        errors.append(f"Item {i} ({item.get('id','?')}): missing content_text")
    if " / " not in item.get("title", ""):
        errors.append(f"Item {i} ({item.get('id','?')}): title missing ' / ' (需要中英双语)")
    if item.get("media"):
        m = item["media"]
        if not m.get("video_url"):
            errors.append(f"Item {i} ({item.get('id','?')}): media missing video_url")

if errors:
    print(f"[Feed校验] ⚠️ {len(errors)} 个问题:")
    for e in errors[:10]:
        print(f"  - {e}")
else:
    print(f"[Feed校验] ✅ {ITEM_COUNT} 条全部通过（id/title/content_text/双语格式）")

# ===== 统计汇总 =====
total_links = 0
pages_with_links = 0
for item in ITEMS:
    tags = item.get("tags", [])
    slug = item.get("url", "").rstrip("/").split("/")[-1].replace(".html", "") or item['id']
    rel = set()
    for t in tags:
        for rit in ITEMS:
            rid = rit["id"]
            rslug = rit.get("url", "").rstrip("/").split("/")[-1].replace(".html", "") or rid
            if t in rit.get("tags", []) and rslug != slug:
                rel.add(rslug)
    lc = min(len(rel), 4)
    total_links += lc
    if lc > 0:
        pages_with_links += 1

print(f"\n{'='*55}")
print(f"[Pipeline v2.0 Complete] 全量产物已生成")
print(f"  产品: {P['name_zh']}")
print(f"  域名: {SITE}")
print(f"  知识原子: {ITEM_COUNT}（文本 {len(text_items)} + 视频 {len(video_items)}）")
print(f"  分类: {len(categories)} 个")
print(f"  sitemap: {len(urls)} URLs")
print(f"  llms.txt: {ITEM_COUNT} 篇索引")
print(f"  交叉链接: {total_links} 条（{pages_with_links}/{ITEM_COUNT} 页有链接）")
print(f"  平均每页: {total_links/max(ITEM_COUNT,1):.1f} 条裂变路径")
print(f"{'='*55}")
print(f"\n[新产品的接入方式]")
print(f"  1. 复制整个目录到新产品名")
print(f"  2. 修改 config.json（产品名/域名/颜色/联系方式）")
print(f"  3. 替换 feed.json（新知识原子，视频加media字段）")
print(f"  4. python3 pipeline.py → 一键全量生成")
print(f"  5. wrangler pages deploy → 部署上线")
print(f"  零调配，零改代码。")
