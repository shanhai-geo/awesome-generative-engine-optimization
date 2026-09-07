#!/usr/bin/env python3
"""
GeoMind API Hub — 统一API中枢系统
====================================
集中管理所有外部API对接：IndexNow推送、百度主动推送、GitHub部署、CDN刷新、站点健康检查。
所有"能走API"的通路统一由此中枢调度，非API操作（需浏览器登录的）不在此范围。

命令：
  python3 api_hub.py status          # 全链路状态检查
  python3 api_hub.py indexnow        # IndexNow批量推送（Bing/Yandex/Naver）
  python3 api_hub.py baidu           # 百度主动推送
  python3 api_hub.py push-all        # 全量推送（IndexNow + 百度）
  python3 api_hub.py deploy          # GitHub Pages 部署
  python3 api_hub.py health          # 站点健康检查
  python3 api_hub.py report          # 综合状态报告
  python3 api_hub.py push-new <url>  # 推送单个新URL到所有引擎
"""

import json
import os
import sys
import re
import base64
import time
import hashlib
import urllib.request
import urllib.error
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path

# ===== 路径与配置 =====
BASE = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(BASE, "config.json")
SITEMAP_PATH = os.path.join(BASE, "sitemap.xml")
FEED_PATH = os.path.join(BASE, "feed.json")
INDEXNOW_KEY_FILE = None  # 从config动态读取
STATE_DIR = os.path.join(BASE, "api_hub_state")
os.makedirs(STATE_DIR, exist_ok=True)

def load_config():
    with open(CONFIG_PATH, encoding="utf-8") as f:
        return json.load(f)

CFG = load_config()
SITE = CFG["domain"]["primary"]
INDEXNOW_KEY = CFG["indexnow"]["key"]

# 敏感凭证从 hub_secrets.json 读取（不进git仓库）
SECRETS_PATH = os.path.join(BASE, "hub_secrets.json")
_secrets = {}
if os.path.exists(SECRETS_PATH):
    with open(SECRETS_PATH, encoding="utf-8") as f:
        _secrets = json.load(f)
BAIDU_TOKEN = _secrets.get("baidu_token", "")
GITHUB_TOKEN = _secrets.get("github_token", "")
GITHUB_REPO = CFG.get("github", {}).get("repo", "shanhai-geo/awesome-generative-engine-optimization")

# ===== 通用HTTP工具 =====
def http_request(url, method="GET", data=None, headers=None, timeout=15, as_json=False):
    """通用HTTP请求封装"""
    req = urllib.request.Request(url, method=method)
    if headers:
        for k, v in headers.items():
            req.add_header(k, v)
    body = None
    if data is not None:
        if isinstance(data, str):
            body = data.encode("utf-8")
        elif isinstance(data, dict):
            body = json.dumps(data).encode("utf-8")
            if "Content-Type" not in (headers or {}):
                req.add_header("Content-Type", "application/json")
        elif isinstance(data, bytes):
            body = data
    try:
        with urllib.request.urlopen(req, data=body, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
            if as_json and raw.strip():
                return {"status": resp.status, "data": json.loads(raw)}
            elif as_json:
                return {"status": resp.status, "data": {}}
            return {"status": resp.status, "data": raw}
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8", errors="replace")
        if raw.strip():
            try:
                return {"status": e.code, "data": json.loads(raw)}
            except:
                pass
        return {"status": e.code, "data": raw if raw else f"HTTP {e.code}"}
    except Exception as e:
        return {"status": 0, "data": str(e)}


# ===== URL收集器 =====
def get_sitemap_urls():
    """从sitemap.xml提取所有URL"""
    urls = []
    try:
        tree = ET.parse(SITEMAP_PATH)
        root = tree.getroot()
        ns = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}
        for url_elem in root.findall("sm:url", ns):
            loc = url_elem.find("sm:loc", ns)
            if loc is not None and loc.text:
                urls.append(loc.text.strip())
    except Exception as e:
        print(f"  [WARN] sitemap解析失败: {e}")
    return urls

def get_feed_urls():
    """从feed.json提取所有URL"""
    urls = []
    try:
        with open(FEED_PATH, encoding="utf-8") as f:
            feed = json.load(f)
        for item in feed.get("items", []):
            if "url" in item:
                urls.append(item["url"])
    except Exception as e:
        print(f"  [WARN] feed解析失败: {e}")
    return urls

def get_all_urls():
    """获取去重后的全量URL列表"""
    urls = set()
    urls.update(get_sitemap_urls())
    urls.update(get_feed_urls())
    # 确保首页和关键页在列
    urls.add(SITE + "/")
    urls.add(SITE + "/llms.txt")
    urls.add(SITE + "/feed.json")
    urls.add(SITE + "/knowledge/")
    urls.add(SITE + "/knowledge/index.html")
    urls.add(SITE + "/knowledge-graph.html")
    return sorted(urls)


# ===== 状态持久化 =====
def load_state():
    state_file = os.path.join(STATE_DIR, "hub_state.json")
    if os.path.exists(state_file):
        with open(state_file, encoding="utf-8") as f:
            return json.load(f)
    return {"indexnow_pushed": [], "baidu_pushed": [], "last_deploy": None, "push_log": []}

def save_state(state):
    state_file = os.path.join(STATE_DIR, "hub_state.json")
    with open(state_file, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)


# ================================================================
# 模块1: IndexNow 批量推送
# ================================================================
def cmd_indexnow(batch_size=100, dry_run=False):
    """IndexNow批量推送 — 向Bing/Yandex/Naver等支持IndexNow的搜索引擎推送URL"""
    print("=" * 60)
    print("📡 IndexNow 批量推送")
    print("=" * 60)

    state = load_state()
    already_pushed = set(state.get("indexnow_pushed", []))
    all_urls = get_all_urls()
    new_urls = [u for u in all_urls if u not in already_pushed]

    print(f"  站点URL总数: {len(all_urls)}")
    print(f"  已推送: {len(already_pushed)}")
    print(f"  待推送: {len(new_urls)}")

    if not new_urls:
        print("  ✅ 全部URL已推送，无需重复操作")
        return {"pushed": 0, "skipped": 0, "errors": 0}

    if dry_run:
        print(f"  [DRY RUN] 将推送 {len(new_urls)} 条URL")
        return {"pushed": 0, "skipped": len(already_pushed), "errors": 0}

    # IndexNow 支持批量推送（最多10000条/次）
    endpoint = CFG["indexnow"]["api_endpoint"]
    total_pushed = 0
    total_errors = 0

    for i in range(0, len(new_urls), batch_size):
        batch = new_urls[i:i + batch_size]
        payload = {
            "host": SITE.replace("https://", "").replace("http://", ""),
            "key": INDEXNOW_KEY,
            "keyLocation": f"{SITE}/{INDEXNOW_KEY}.txt",
            "urlList": batch
        }
        result = http_request(endpoint, method="POST", data=payload, timeout=30, as_json=True)

        if result["status"] in (200, 202):
            total_pushed += len(batch)
            print(f"  ✅ 批次 {i // batch_size + 1}: {len(batch)} URLs 推送成功")
            for u in batch:
                already_pushed.add(u)
        else:
            total_errors += len(batch)
            print(f"  ❌ 批次 {i // batch_size + 1}: 失败 HTTP {result['status']} — {str(result['data'])[:100]}")

        # 避免触发限流
        if i + batch_size < len(new_urls):
            time.sleep(1)

    # 保存状态
    state["indexnow_pushed"] = sorted(already_pushed)
    state["push_log"].append({
        "action": "indexnow",
        "time": datetime.now().isoformat(),
        "pushed": total_pushed,
        "errors": total_errors
    })
    # 只保留最近100条日志
    state["push_log"] = state["push_log"][-100:]
    save_state(state)

    print(f"\n  汇总: 成功 {total_pushed} / 失败 {total_errors}")
    return {"pushed": total_pushed, "skipped": len(all_urls) - len(new_urls), "errors": total_errors}


# ================================================================
# 模块2: 百度主动推送
# ================================================================
def cmd_baidu(batch_size=2000, dry_run=False):
    """百度主动推送 — 每次最多推送2000条（百度API限制）"""
    print("=" * 60)
    print("📡 百度主动推送")
    print("=" * 60)

    state = load_state()
    already_pushed = set(state.get("baidu_pushed", []))
    all_urls = get_all_urls()
    new_urls = [u for u in all_urls if u not in already_pushed]

    print(f"  站点URL总数: {len(all_urls)}")
    print(f"  已推送: {len(already_pushed)}")
    print(f"  待推送: {len(new_urls)}")

    if not new_urls:
        print("  ✅ 全部URL已推送至百度")
        return {"pushed": 0, "skipped": 0, "errors": 0}

    if dry_run:
        print(f"  [DRY RUN] 将推送 {len(new_urls)} 条URL到百度")
        return {"pushed": 0, "skipped": len(already_pushed), "errors": 0}

    endpoint = f"http://data.zz.baidu.com/urls?site={SITE}&token={BAIDU_TOKEN}"
    total_pushed = 0
    total_errors = 0
    today_remaining = None

    for i in range(0, len(new_urls), batch_size):
        batch = new_urls[i:i + batch_size]
        body = "\n".join(batch)
        result = http_request(
            endpoint, method="POST",
            data=body,
            headers={"Content-Type": "text/plain"},
            timeout=30, as_json=True
        )

        data = result.get("data", {})
        if result["status"] == 200 and isinstance(data, dict):
            success = data.get("success", 0)
            remain = data.get("remain", 0)
            total_pushed += success
            today_remaining = remain
            for u in batch[:success]:
                already_pushed.add(u)
            print(f"  ✅ 批次 {i // batch_size + 1}: 成功 {success}, 剩余配额 {remain}")
            if remain == 0:
                print("  ⚠️ 今日配额已用完，剩余URL将在下次执行时推送")
                break
        else:
            error_msg = data.get("message", str(data)) if isinstance(data, dict) else str(data)
            if "over quota" in error_msg.lower():
                print(f"  ⚠️ 百度今日配额已用完（{error_msg}），剩余URL将在下次执行时推送")
                today_remaining = 0
                break
            total_errors += len(batch)
            print(f"  ❌ 批次 {i // batch_size + 1}: {error_msg}")

        if i + batch_size < len(new_urls):
            time.sleep(2)

    # 保存状态
    state["baidu_pushed"] = sorted(already_pushed)
    state["push_log"].append({
        "action": "baidu",
        "time": datetime.now().isoformat(),
        "pushed": total_pushed,
        "errors": total_errors,
        "remaining": today_remaining
    })
    state["push_log"] = state["push_log"][-100:]
    save_state(state)

    print(f"\n  汇总: 成功 {total_pushed} / 失败 {total_errors}" + 
          (f" / 剩余配额 {today_remaining}" if today_remaining is not None else ""))
    return {"pushed": total_pushed, "skipped": len(all_urls) - len(new_urls) - total_pushed, "errors": total_errors}


# ================================================================
# 模块3: GitHub Pages 部署
# ================================================================
def cmd_deploy(message=None):
    """通过GitHub Git Data API部署到GitHub Pages"""
    print("=" * 60)
    print("📦 GitHub Pages 部署")
    print("=" * 60)

    GITHUB_BASE = f"https://api.github.com/repos/{GITHUB_REPO}"
    auth_headers = {
        "Authorization": f"token {GITHUB_TOKEN}",
        "Accept": "application/vnd.github+json",
        "User-Agent": "geo-api-hub"
    }

    # 排除规则
    EXCLUDE_FILES = {
        "gh_api_push.py", "api_hub.py", "pipeline.py",
        "fix_data_v4.py", "fix_data_v4b.py", "fix_data_v4c.py", "fix_data_v3.py",
        "surge_deploy.sh", "build_knowledge.py", "upgrade_feed_nuclear.py",
        "upgrade_schema_v2.py", "remove_fake_expert.py",
    }
    EXCLUDE_EXTS = {".py", ".pyc", ".log", ".bak", ".tar.gz", ".tmp", ".pdf"}
    EXCLUDE_DIRS = {"__pycache__", ".git", "node_modules", ".well-known-backup", "api_hub_state"}

    # 1. 收集文件
    print("  收集本地文件...")
    files = []
    for root, dirs, filenames in os.walk(BASE):
        dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS and not d.startswith("knowledge_backup_")]
        for fname in filenames:
            if fname in EXCLUDE_FILES:
                continue
            if any(fname.endswith(ext) for ext in EXCLUDE_EXTS):
                continue
            if fname.startswith(".") and not fname.startswith(".well-known") and fname not in (".nojekyll", ".gitignore", "_headers", "_redirects"):
                continue
            fpath = os.path.join(root, fname)
            rel = os.path.relpath(fpath, BASE)
            files.append((rel, fpath))
    files.sort()
    print(f"  待部署文件: {len(files)}")

    # 2. 获取远端HEAD
    print("  获取远端HEAD...")
    ref_resp = http_request(f"{GITHUB_BASE}/git/ref/heads/main", headers=auth_headers, as_json=True)
    if ref_resp["status"] != 200:
        print(f"  ❌ 获取HEAD失败: {ref_resp}")
        return {"success": False, "error": "获取HEAD失败"}
    head_sha = ref_resp["data"]["object"]["sha"]
    print(f"  HEAD: {head_sha[:12]}")

    # 3. 创建blob
    print("  创建blob对象...")
    tree_items = []
    for i, (repo_path, local_path) in enumerate(files):
        with open(local_path, "rb") as f:
            content = base64.b64encode(f.read()).decode()
        blob_resp = http_request(
            f"{GITHUB_BASE}/git/blobs",
            method="POST",
            data={"content": content, "encoding": "base64"},
            headers=auth_headers, as_json=True
        )
        if blob_resp["status"] in (200, 201):
            tree_items.append({
                "path": repo_path,
                "mode": "100644",
                "type": "blob",
                "sha": blob_resp["data"]["sha"]
            })
        else:
            print(f"  ⚠️ blob失败: {repo_path} → {blob_resp['status']}")
        if (i + 1) % 50 == 0:
            print(f"    blob进度: {i + 1}/{len(files)}")
    print(f"  blob完成: {len(tree_items)}/{len(files)}")

    # 4. 获取base tree
    commit_resp = http_request(f"{GITHUB_BASE}/git/commits/{head_sha}", headers=auth_headers, as_json=True)
    base_tree = commit_resp["data"]["tree"]["sha"]

    # 5. 创建new tree
    new_tree_resp = http_request(
        f"{GITHUB_BASE}/git/trees",
        method="POST",
        data={"base_tree": base_tree, "tree": tree_items},
        headers=auth_headers, as_json=True
    )
    new_tree_sha = new_tree_resp["data"]["sha"]
    print(f"  新tree: {new_tree_sha[:12]}")

    # 6. 创建commit
    if not message:
        message = f"deploy: API Hub auto-deploy {len(files)} files at {datetime.now().strftime('%Y-%m-%d %H:%M')}"
    new_commit_resp = http_request(
        f"{GITHUB_BASE}/git/commits",
        method="POST",
        data={"message": message, "tree": new_tree_sha, "parents": [head_sha]},
        headers=auth_headers, as_json=True
    )
    new_commit_sha = new_commit_resp["data"]["sha"]
    print(f"  新commit: {new_commit_sha[:12]}")

    # 7. 更新ref
    update_resp = http_request(
        f"{GITHUB_BASE}/git/refs/heads/main",
        method="PATCH",
        data={"sha": new_commit_sha, "force": True},
        headers=auth_headers, as_json=True
    )

    if update_resp["status"] == 200:
        print(f"  ✅ 部署成功: {new_commit_sha[:12]}")
        state = load_state()
        state["last_deploy"] = {
            "time": datetime.now().isoformat(),
            "commit": new_commit_sha,
            "files": len(files)
        }
        save_state(state)
        return {"success": True, "commit": new_commit_sha, "files": len(files)}
    else:
        print(f"  ❌ 更新ref失败: {update_resp}")
        return {"success": False, "error": str(update_resp)}


# ================================================================
# 模块4: 站点健康检查
# ================================================================
def cmd_health():
    """站点健康检查 — 验证核心URL可用性"""
    print("=" * 60)
    print("🏥 站点健康检查")
    print("=" * 60)

    critical_paths = [
        "/", "/llms.txt", "/llms-full.txt", "/feed.json",
        "/sitemap.xml", "/robots.txt", "/knowledge/",
        "/knowledge/index.html", "/knowledge-graph.html",
        "/data/factory-directory.json", "/data/price-tracker.json",
        f"/{INDEXNOW_KEY}.txt"
    ]

    results = []
    all_ok = True
    for path in critical_paths:
        url = SITE + path
        resp = http_request(url, timeout=10)
        status = "✅" if resp["status"] == 200 else "❌"
        if resp["status"] != 200:
            all_ok = False
        size = len(resp.get("data", "")) if isinstance(resp.get("data"), str) else 0
        results.append({"path": path, "status": resp["status"], "size": size})
        print(f"  {status} {path} → HTTP {resp['status']} ({size} bytes)")

    # robots.txt 检查 AI 爬虫
    robots_resp = http_request(SITE + "/robots.txt", timeout=10)
    if robots_resp["status"] == 200:
        robots_text = robots_resp["data"]
        ai_bots = ["GPTBot", "ClaudeBot", "PerplexityBot", "Bytespider", "Google-Extended", "CCBot", "Baiduspider"]
        print(f"\n  AI爬虫策略:")
        for bot in ai_bots:
            found = bot in robots_text and "Allow" in robots_text.split(bot)[1].split("\n")[0] if bot in robots_text else False
            icon = "✅" if found else "❌"
            print(f"    {icon} {bot}: {'Allow' if found else '未找到'}")

    return {"all_ok": all_ok, "checks": results}


# ================================================================
# 模块5: 全链路状态检查
# ================================================================
def cmd_status():
    """全链路状态检查 — 一次性检查所有API通路"""
    print("=" * 60)
    print("🔍 全链路状态检查")
    print("=" * 60)

    status = {}

    # 1. 站点可达性
    print("\n  [1/5] 站点可达性")
    resp = http_request(SITE + "/", timeout=10)
    status["site"] = resp["status"] == 200
    print(f"    {'✅' if status['site'] else '❌'} {SITE} → HTTP {resp['status']}")

    # 2. IndexNow API
    print("\n  [2/5] IndexNow API")
    test_url = SITE + "/"
    in_resp = http_request(
        f"https://api.indexnow.org/indexnow?url={test_url}&key={INDEXNOW_KEY}",
        timeout=10
    )
    status["indexnow"] = in_resp["status"] in (200, 202)
    print(f"    {'✅' if status['indexnow'] else '❌'} IndexNow → HTTP {in_resp['status']}")

    # 3. 百度推送API
    print("\n  [3/5] 百度推送API")
    bd_resp = http_request(
        f"http://data.zz.baidu.com/urls?site={SITE}&token={BAIDU_TOKEN}",
        method="POST",
        data=test_url,
        headers={"Content-Type": "text/plain"},
        timeout=10, as_json=True
    )
    bd_data = bd_resp.get("data", {})
    # over quota 说明通路正常只是配额用完
    bd_msg = bd_data.get("message", "") if isinstance(bd_data, dict) else str(bd_data)
    status["baidu_api"] = bd_resp["status"] == 200 or "over quota" in str(bd_msg).lower()
    status["baidu_quota_exhausted"] = "over quota" in str(bd_msg).lower()
    bd_icon = "✅" if status["baidu_api"] else "❌"
    if status.get("baidu_quota_exhausted"):
        bd_detail = "配额已用完(通路正常)"
    else:
        bd_detail = "HTTP " + str(bd_resp["status"])
    print(f"    {bd_icon} 百度API → {bd_detail}")

    # 4. GitHub API
    print("\n  [4/5] GitHub API")
    gh_resp = http_request(
        f"https://api.github.com/repos/{GITHUB_REPO}",
        headers={"Authorization": f"token {GITHUB_TOKEN}"},
        timeout=10, as_json=True
    )
    status["github"] = gh_resp["status"] == 200
    print(f"    {'✅' if status['github'] else '❌'} GitHub API → HTTP {gh_resp['status']}")

    # 5. 推送状态
    print("\n  [5/5] 推送状态")
    state = load_state()
    all_urls = get_all_urls()
    in_pushed = len(state.get("indexnow_pushed", []))
    bd_pushed_len = len(state.get("baidu_pushed", []))
    status["indexnow_pushed"] = in_pushed
    status["baidu_pushed"] = bd_pushed_len
    status["total_urls"] = len(all_urls)
    print(f"    IndexNow: {in_pushed}/{len(all_urls)} URLs 已推送")
    print(f"    百度: {bd_pushed_len}/{len(all_urls)} URLs 已推送")
    if state.get("last_deploy"):
        print(f"    最近部署: {state['last_deploy']['time'][:19]} ({state['last_deploy']['files']} files)")

    # 汇总
    print("\n" + "=" * 60)
    core_pass = all([status.get("site"), status.get("indexnow"), status.get("baidu_api"), status.get("github")])
    print(f"  核心通路: {'✅ 全部正常' if core_pass else '❌ 存在异常'}")
    print(f"  IndexNow覆盖率: {in_pushed}/{len(all_urls)} ({100*in_pushed//max(len(all_urls),1)}%)")
    print(f"  百度覆盖率: {bd_pushed_len}/{len(all_urls)} ({100*bd_pushed_len//max(len(all_urls),1)}%)")
    print("=" * 60)

    return status


# ================================================================
# 模块6: 综合报告
# ================================================================
def cmd_report():
    """生成综合状态报告"""
    print("=" * 60)
    print("📊 GeoMind API Hub 综合报告")
    print(f"   生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)

    # 运行全链路检查
    status = cmd_status()

    # 推送历史
    state = load_state()
    log = state.get("push_log", [])
    if log:
        print(f"\n  最近推送记录 (共{len(log)}条):")
        for entry in log[-10:]:
            t = entry.get("time", "")[:19]
            action = entry.get("action", "")
            pushed = entry.get("pushed", 0)
            errors = entry.get("errors", 0)
            print(f"    {t} | {action}: +{pushed} URLs, {errors} errors")

    return status


# ================================================================
# 模块7: 单URL推送
# ================================================================
def cmd_push_new(url):
    """推送单个新URL到所有引擎"""
    print(f"📡 推送新URL: {url}")
    results = {}

    # IndexNow
    in_resp = http_request(
        f"https://api.indexnow.org/indexnow?url={url}&key={INDEXNOW_KEY}",
        timeout=10
    )
    results["indexnow"] = in_resp["status"] in (200, 202)
    print(f"  IndexNow: {'✅' if results['indexnow'] else '❌'} HTTP {in_resp['status']}")

    # 百度
    bd_resp = http_request(
        f"http://data.zz.baidu.com/urls?site={SITE}&token={BAIDU_TOKEN}",
        method="POST", data=url,
        headers={"Content-Type": "text/plain"},
        timeout=10, as_json=True
    )
    bd_data = bd_resp.get("data", {})
    bd_success = bd_data.get("success", 0) if isinstance(bd_data, dict) else 0
    results["baidu"] = bd_success > 0 or bd_resp["status"] == 200
    print(f"  百度: {'✅' if results['baidu'] else '❌'} {bd_data}")

    # 更新状态
    state = load_state()
    if url not in state.get("indexnow_pushed", []):
        state.setdefault("indexnow_pushed", []).append(url)
    if url not in state.get("baidu_pushed", []):
        state.setdefault("baidu_pushed", []).append(url)
    save_state(state)

    return results


# ================================================================
# 主入口
# ================================================================
def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    cmd = sys.argv[1].lower()

    if cmd == "status":
        cmd_status()
    elif cmd == "indexnow":
        dry = "--dry-run" in sys.argv
        cmd_indexnow(dry_run=dry)
    elif cmd == "baidu":
        dry = "--dry-run" in sys.argv
        cmd_baidu(dry_run=dry)
    elif cmd == "push-all":
        print("🚀 全量推送启动\n")
        cmd_indexnow()
        print()
        cmd_baidu()
    elif cmd == "deploy":
        msg = None
        if "--msg" in sys.argv:
            idx = sys.argv.index("--msg")
            if idx + 1 < len(sys.argv):
                msg = sys.argv[idx + 1]
        cmd_deploy(message=msg)
    elif cmd == "health":
        cmd_health()
    elif cmd == "report":
        cmd_report()
    elif cmd == "push-new":
        if len(sys.argv) < 3:
            print("用法: python3 api_hub.py push-new <url>")
            sys.exit(1)
        cmd_push_new(sys.argv[2])
    else:
        print(f"未知命令: {cmd}")
        print(__doc__)
        sys.exit(1)


if __name__ == "__main__":
    main()
