#!/usr/bin/env python3
"""
赚客吧论坛监控 + Server酱微信推送 (GitHub Actions 版)
监控页面: http://www.zuanke8.com/forum-15-1.html
"""

import json
import os
import re
import sys
from datetime import datetime

import requests
from bs4 import BeautifulSoup

# ============ 配置 ============
URL = "http://www.zuanke8.com/forum-15-1.html"
SCT_SENDKEY = os.environ.get("SCT_SENDKEY", "")
DATA_FILE = "zuanke8_posts.json"
MAX_PUSH = 10


def fetch_page(url):
    resp = requests.get(url, headers={
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept-Language": "zh-CN,zh;q=0.9",
    }, timeout=15)
    resp.encoding = "gbk"
    return resp.text


def parse_posts(html):
    soup = BeautifulSoup(html, "html.parser")
    posts = []
    thread_pattern = re.compile(r"thread-(\d+)-")

    for link in soup.find_all("a", class_="xst"):
        href = link.get("href", "")
        m = thread_pattern.search(href)
        if not m:
            continue

        tid = m.group(1)
        title = link.get_text(strip=True)
        if not title or len(title) < 2:
            continue

        full_url = href if href.startswith("http") else "http://www.zuanke8.com" + href

        author, post_time = "", ""
        tbody = link.find_parent("tbody")
        if tbody:
            if (tbody.get("id") or "").startswith("stickthread_"):
                continue
            cite = tbody.find("cite")
            if cite:
                a = cite.find("a")
                if a:
                    author = a.get_text(strip=True)
            for em in tbody.find_all("em"):
                tm = re.search(r"(\d{4}[-/]\d{1,2}[-/]\d{1,2}\s*\d{1,2}:\d{2})", em.get_text(strip=True))
                if tm:
                    post_time = tm.group(1)
                    break

        posts.append({"id": tid, "title": title, "url": full_url, "author": author, "time": post_time})

    return posts


def load_previous():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return {p["id"]: p for p in json.load(f).get("posts", [])}
    return {}


def save_posts(posts):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump({"updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "posts": posts}, f, ensure_ascii=False, indent=2)


def push_wechat(title, content):
    if not SCT_SENDKEY:
        print("[SKIP] 未配置 SCT_SENDKEY")
        return
    url = f"https://sctapi.ftqq.com/{SCT_SENDKEY}.send"
    resp = requests.post(url, data={"title": title, "desp": content}, timeout=10)
    r = resp.json()
    if r.get("code") == 0:
        print(f"[Server酱] 推送成功: {title}")
    else:
        print(f"[Server酱] 推送失败: {r}")


def main():
    print(f"[{datetime.now()}] 开始监控...")

    html = fetch_page(URL)
    current = parse_posts(html)
    print(f"解析到 {len(current)} 条帖子")

    previous = load_previous()
    new_posts = [p for p in current if p["id"] not in previous]

    if new_posts:
        print(f"发现 {len(new_posts)} 条新帖")
        if previous:
            lines = [f"## 赚客大家谈 · 新帖速递\n", f"**{len(new_posts)}** 条新帖\n"]
            for i, p in enumerate(new_posts[:MAX_PUSH], 1):
                t = f" _{p['time']}_" if p["time"] else ""
                lines.append(f"{i}. [{p['title']}]({p['url']}){t}")
            if len(new_posts) > MAX_PUSH:
                lines.append(f"\n> 还有 {len(new_posts) - MAX_PUSH} 条新帖")
            lines.append(f"\n---\n{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            push_wechat(f"赚客吧新帖 ({len(new_posts)}条)", "\n".join(lines))
        else:
            print("首次运行，建立基线")
    else:
        print("没有新帖子")

    save_posts(current)

    # GitHub Actions: 输出是否有新帖，供后续 step 判断是否 commit
    with open(os.environ.get("GITHUB_OUTPUT", "/dev/null"), "a") as f:
        f.write(f"has_new={'true' if new_posts and previous else 'false'}\n")


if __name__ == "__main__":
    main()
