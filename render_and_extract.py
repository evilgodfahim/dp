# render_and_extract.py
#!/usr/bin/env python3
"""
Render the opinion page with Playwright (Chromium), save opinion.html,
extract JSON-like data from the page, normalize items and write feed.xml.
Keeps previous GUIDs from feed.xml to preserve history.
"""

import re
import json
import sys
from pathlib import Path
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright
from html import escape as html_escape

HTML_FILE = Path("opinion.html")
FEED_FILE = Path("feed.xml")
MAX_ITEMS = 500
URL = "https://www.dhakapost.com/opinion"

def auto_scroll(page):
    page.evaluate("""
    async () => {
      await new Promise(resolve => {
        var total = 0;
        var distance = 500;
        var timer = setInterval(() => {
          window.scrollBy(0, distance);
          total += distance;
          if (total > document.body.scrollHeight - window.innerHeight) {
            clearInterval(timer);
            resolve();
          }
        }, 300);
      });
    }
    """)

def render_page(url, output_path):
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=["--no-sandbox","--disable-setuid-sandbox","--disable-dev-shm-usage"])
        try:
            page = browser.new_page(viewport={"width":1280, "height":900})
            page.goto(url, wait_until="networkidle", timeout=90000)
            auto_scroll(page)
            # wait for likely content or text length
            try:
                page.wait_for_selector("article, .post, .td_block_inner, .single-post", timeout=90000)
            except Exception:
                pass
            page.wait_for_timeout(2000)
            html = page.content()
            output_path.write_text(html, encoding="utf8")
            return html
        finally:
            try:
                browser.close()
            except Exception:
                pass

# --- JSON-like extraction utilities ---
def find_balanced_object(s, start_idx):
    if start_idx < 0 or start_idx >= len(s) or s[start_idx] != "{":
        return None
    i = start_idx
    depth = 0
    while i < len(s):
        ch = s[i]
        if ch == '"' or ch == "'":
            quote = ch
            i += 1
            while i < len(s):
                if s[i] == "\\":
                    i += 2
                    continue
                if s[i] == quote:
                    i += 1
                    break
                i += 1
            continue
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return s[start_idx:i+1]
        i += 1
    return None

def sanitize_js_object(raw):
    # remove block comments and single-line comments
    no_block = re.sub(r"/\*[\s\S]*?\*/", "", raw)
    no_line = re.sub(r"//[^\n\r]*", "", no_block)
    # remove trailing commas before } or ]
    no_trailing = re.sub(r",\s*([}\]])", r"\1", no_line)
    # convert simple single-quoted strings to JSON double-quoted strings
    def replace_single_quote(m):
        inner = m.group(1)
        # inner may contain escaped chars; decode escapes for safe re-encoding
        # We will leave escapes as-is and let json.loads handle them after wrapping via json.dumps
        return json.dumps(inner)
    # This regex targets '...'; it will not perfectly handle every JS edge-case but handles common cases.
    converted = re.sub(r"'([^'\\]*(?:\\.[^'\\]*)*)'", replace_single_quote, no_trailing)
    return converted

def extract_json_like(html):
    labels = [
        "initialContents",
        "initial_contents",
        "__INITIAL_STATE__",
        "window.__INITIAL_STATE__",
        "window.initialContents",
        "INITIAL_STATE"
    ]
    for label in labels:
        idx = html.find(label)
        if idx == -1:
            continue
        brace_idx = html.find("{", idx)
        if brace_idx == -1:
            continue
        raw = find_balanced_object(html, brace_idx)
        if not raw:
            continue
        cleaned = sanitize_js_object(raw)
        try:
            return json.loads(cleaned)
        except Exception:
            # if parsing fails, continue to next label
            continue

    # fallback: script type="application/json"
    for script in re.finditer(r'<script[^>]*type=["\']application/json["\'][^>]*>([\s\S]*?)</script>', html, flags=re.IGNORECASE):
        try:
            return json.loads(script.group(1))
        except Exception:
            pass

    # fallback: try generic <script> ... var something = { ... } ... </script>
    for m in re.finditer(r"<script[^>]*>([\s\S]*?)</script>", html, flags=re.IGNORECASE):
        script_text = m.group(1)
        for lab_m in re.finditer(r"([A-Za-z0-9_\$]+)\s*[:=]\s*{", script_text):
            brace_pos = m.start(1) + script_text.find("{", lab_m.start())
            raw = find_balanced_object(html, brace_pos)
            if not raw:
                continue
            cleaned = sanitize_js_object(raw)
            try:
                return json.loads(cleaned)
            except Exception:
                continue
    return None

# --- feed utilities ---
def load_old_guids(feed_path):
    if not feed_path.exists():
        return []
    txt = feed_path.read_text(encoding="utf8")
    return [m.group(1).strip() for m in re.finditer(r"<guid[^>]*>([\s\S]*?)</guid>", txt)]

def build_rss(items):
    head = '<?xml version="1.0" encoding="UTF-8"?>\n<rss version="2.0">\n<channel>\n'
    head += '<title>DhakaPost Opinion Feed</title>\n<link>https://www.dhakapost.com/opinion</link>\n<description>Generated</description>\n'
    tail = "\n</channel>\n</rss>\n"
    body = ""
    for i in items:
        title = i.get("title","")
        url = i.get("url","")
        brief = i.get("brief","")
        body += "<item>\n"
        body += f"  <title><![CDATA[{title}]]></title>\n"
        body += f"  <link>{html_escape(url)}</link>\n"
        body += f"  <guid>{html_escape(url)}</guid>\n"
        body += f"  <description><![CDATA[{brief}]]></description>\n"
        body += "</item>\n"
    return head + body + tail

def normalize_items(raw):
    if raw is None:
        return []
    if isinstance(raw, list):
        data_items = raw
    elif isinstance(raw, dict):
        if isinstance(raw.get("items"), list):
            data_items = raw["items"]
        elif isinstance(raw.get("contents"), list):
            data_items = raw["contents"]
        elif isinstance(raw.get("articles"), list):
            data_items = raw["articles"]
        else:
            arrp = next((raw[k] for k in raw if isinstance(raw[k], list)), [])
            data_items = arrp or []
    else:
        data_items = []

    out = []
    for i in data_items:
        if not isinstance(i, dict):
            continue
        url = i.get("URL") or i.get("url") or i.get("link") or i.get("href") or i.get("path")
        title = i.get("Heading") or i.get("title") or i.get("heading") or i.get("name") or i.get("headline")
        brief = i.get("Brief") or i.get("brief") or i.get("summary") or i.get("excerpt") or i.get("snippet") or ""
        if not url:
            continue
        out.append({"url": str(url).strip(), "title": str(title or "").strip(), "brief": str(brief or "").strip()})
    return out

def main():
    try:
        html = None
        if not HTML_FILE.exists():
            html = render_page(URL, HTML_FILE)
        else:
            html = HTML_FILE.read_text(encoding="utf8")
        if not html:
            print("No HTML captured", file=sys.stderr)
            sys.exit(1)

        raw = extract_json_like(html) or {}
        new_items = normalize_items(raw)

        old_guids = load_old_guids(FEED_FILE)
        old_set = set(old_guids)

        merged = [i for i in new_items if i["url"] not in old_set]
        merged += [{"url": u, "title": "", "brief": ""} for u in old_guids if not any(n["url"] == u for n in new_items)]

        final = merged[:MAX_ITEMS]
        xml = build_rss(final)
        FEED_FILE.write_text(xml, encoding="utf8")
        print(f"Wrote {FEED_FILE} ({len(final)} items)")
    except Exception as e:
        print("error:", e, file=sys.stderr)
        raise

if __name__ == "__main__":
    main()