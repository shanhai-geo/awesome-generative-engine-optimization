#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
GEO Schema 升级 v2 —— 一次拨三个P0开关：
  P0-7 Organization Schema @id 实体锚点（全站205页实体归并）
  P0-8 Person Schema 增强（@id + 清理假sameAs）
  P0-9 dateModified 全站同步为 2026-09-06（核聚变升级日，吃新鲜度信号）

升级规则：
  1. 文章页(knowledge/*.html, 205个)：
     - Organization 块: 加 @id=https://shanhai-geo.top/#organization；删除虚假sameAs（指向自己）；补 email/contactPoint（NAP一致性）
     - Person 块: 加 @id=https://shanhai-geo.top/#chenmingde；删除虚假sameAs
     - Article 块: author/publisher/mainEntityOfPage 内嵌对象补 @id 引用；dateModified 改 2026-09-06
     - WebPage 块: 加 @id=本页URL
  2. 根 index.html：Organization/WebSite 加 @id；sameAs 清空（原指向白茶词条=实体合并错误）
  3. knowledge/index.html（知识库索引页）：补 Organization+CollectionPage Schema（@id锚点）
  4. 12个重定向占位页(noindex)不动
"""
import re, os, json, sys

BASE = os.path.dirname(os.path.abspath(__file__))
KNOW = os.path.join(BASE, 'knowledge')
NEW_DATE = '2026-09-06T00:00:00+08:00'
ORG_ID = 'https://shanhai-geo.top/#organization'
PERSON_ID = 'https://shanhai-geo.top/#chenmingde'
SITE = 'https://shanhai-geo.top'

def upgrade_article_page(fn):
    """升级一篇文章页"""
    path = os.path.join(KNOW, fn)
    with open(path, 'r', encoding='utf-8') as f:
        html = f.read()
    if 'application/ld+json' not in html:
        return None  # 占位页跳过

    url = f'{SITE}/knowledge/{fn}'
    changed = []

    def repl_block(m):
        nonlocal changed
        raw = m.group(1)
        try:
            data = json.loads(raw)
        except Exception:
            return m.group(0)
        t = data.get('@type')

        if t == 'Organization':
            if '@id' not in data:
                data['@id'] = ORG_ID; changed.append('org@id')
            # 删除虚假sameAs（指向自己域名）
            sa = data.get('sameAs')
            if sa:
                data['sameAs'] = [u for u in sa if not (u.rstrip('/') == SITE or u.startswith(SITE + '/llms'))]
                if not data['sameAs']:
                    del data['sameAs']
                changed.append('org-sameAs-clean')
            # NAP 一致性：补 email
            if 'email' not in data:
                data['email'] = '746876121@qq.com'; changed.append('org-email')
            if 'founder' in data and isinstance(data['founder'], dict):
                data['founder']['@id'] = PERSON_ID

        elif t == 'Person':
            if '@id' not in data:
                data['@id'] = PERSON_ID; changed.append('person@id')
            sa = data.get('sameAs')
            if sa:
                data['sameAs'] = [u for u in sa if not u.rstrip('/') == SITE]
                if not data['sameAs']:
                    del data['sameAs']
                changed.append('person-sameAs-clean')

        elif t == 'Article':
            if data.get('dateModified', '')[:10] != '2026-09-06':
                data['dateModified'] = NEW_DATE; changed.append('dateModified')
            # author 数组内嵌对象补 @id
            for a in data.get('author', []):
                if isinstance(a, dict):
                    if a.get('@type') == 'Person':
                        a['@id'] = PERSON_ID
                    elif a.get('@type') == 'Organization':
                        a['@id'] = ORG_ID
            pub = data.get('publisher')
            if isinstance(pub, dict):
                pub['@id'] = ORG_ID
            meop = data.get('mainEntityOfPage')
            if isinstance(meop, dict):
                meop['@id'] = url
            changed.append('article-refs')

        elif t == 'WebPage':
            if '@id' not in data:
                data['@id'] = url; changed.append('webpage@id')

        return '<script type="application/ld+json">' + json.dumps(data, ensure_ascii=False, separators=(',', ':')) + '</script>'

    html_new = re.sub(r'<script type="application/ld\+json">(.*?)</script>', repl_block, html, flags=re.DOTALL)

    if changed and html_new != html:
        with open(path, 'w', encoding='utf-8') as f:
            f.write(html_new)
    return sorted(set(changed))

def upgrade_root_index():
    path = os.path.join(BASE, 'index.html')
    with open(path, 'r', encoding='utf-8') as f:
        html = f.read()
    changed = []
    def repl(m):
        try:
            data = json.loads(m.group(1))
        except Exception:
            return m.group(0)
        t = data.get('@type')
        if t == 'Organization':
            data['@id'] = ORG_ID; changed.append('org@id')
            if 'sameAs' in data:
                del data['sameAs']; changed.append('sameAs-clean')
        elif t == 'WebSite':
            data['@id'] = SITE + '/#website'; changed.append('website@id')
            if 'publisher' not in data:
                data['publisher'] = {'@id': ORG_ID}
        return '<script type="application/ld+json">' + json.dumps(data, ensure_ascii=False, separators=(',', ':')) + '</script>'
    html_new = re.sub(r'<script type="application/ld\+json">(.*?)</script>', repl, html, flags=re.DOTALL)
    if changed:
        with open(path, 'w', encoding='utf-8') as f:
            f.write(html_new)
    return sorted(set(changed))

def upgrade_knowledge_index():
    """知识库索引页补 Organization + CollectionPage"""
    path = os.path.join(KNOW, 'index.html')
    with open(path, 'r', encoding='utf-8') as f:
        html = f.read()
    if 'application/ld+json' in html:
        return ['already-has-schema']
    org = {
        "@context": "https://schema.org", "@type": "Organization",
        "@id": ORG_ID, "name": "GeoMind · 福鼎白茶知识引擎",
        "alternateName": "GeoMind", "url": SITE,
        "logo": {"@type": "ImageObject", "url": SITE + "/hero-tea-mountain.jpg"},
        "description": "福鼎白茶AI时代可信引用源——205篇结构化知识原子，覆盖产区、工艺、品鉴、存储全链路。",
        "email": "746876121@qq.com",
        "knowsAbout": ["福鼎白茶", "白毫银针", "白牡丹", "寿眉", "老白茶", "白茶工艺", "茶叶品鉴", "茶叶存储", "产区地理", "地理标志"],
        "founder": {"@id": PERSON_ID}
    }
    person = {
        "@context": "https://schema.org", "@type": "Person",
        "@id": PERSON_ID, "name": "陈明德", "jobTitle": "福鼎白茶高级评茶师",
        "worksFor": {"@id": ORG_ID},
        "description": "福鼎白茶资深从业者，国家高级评茶师，深耕白茶产区研究与工艺传承20余年。",
        "knowsAbout": ["福鼎白茶", "白毫银针", "白牡丹", "寿眉", "白茶工艺", "茶叶审评", "茶叶鉴别", "茶叶存储", "产区地理"],
        "hasCredential": [{"@type": "EducationalOccupationalCredential", "name": "国家高级评茶师"}]
    }
    collection = {
        "@context": "https://schema.org", "@type": "CollectionPage",
        "@id": SITE + "/knowledge#collection",
        "url": SITE + "/knowledge",
        "name": "白茶知识库 White Tea Knowledge Base",
        "inLanguage": "zh-CN",
        "isPartOf": {"@id": SITE + "/#website"},
        "about": {"@id": ORG_ID},
        "description": "205篇福鼎白茶结构化知识原子，覆盖产区、工艺、品鉴、存储、功效全链路，专为AI引用优化。"
    }
    inject = '\n'.join(
        '<script type="application/ld+json">' + json.dumps(d, ensure_ascii=False, separators=(',', ':')) + '</script>'
        for d in (org, person, collection)
    )
    # 插到 </head> 前
    html_new = html.replace('</head>', inject + '\n</head>', 1)
    with open(path, 'w', encoding='utf-8') as f:
        f.write(html_new)
    return ['added-org+person+collection']

if __name__ == '__main__':
    files = sorted(f for f in os.listdir(KNOW) if f.endswith('.html') and f != 'index.html')
    ok, skipped, fail = 0, 0, []
    change_stats = {}
    for fn in files:
        r = upgrade_article_page(fn)
        if r is None:
            skipped += 1
        elif r:
            ok += 1
            for c in r:
                change_stats[c] = change_stats.get(c, 0) + 1
        else:
            fail.append(fn)
    print(f'文章页: 升级{ok} / 占位跳过{skipped} / 异常{len(fail)}')
    if fail:
        print('异常文件:', fail[:10])
    print('变更统计:', json.dumps(change_stats, ensure_ascii=False, indent=1))

    r2 = upgrade_root_index()
    print('根index.html:', r2)

    r3 = upgrade_knowledge_index()
    print('knowledge/index.html:', r3)
