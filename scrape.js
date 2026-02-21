#!/usr/bin/env node
"use strict";

/*
Full extractor.js
- robust extractJSON that handles JS-ish objects in rendered HTML
- reads opinion.html (rendered snapshot)
- builds feed.xml from extracted items, preserving previous GUIDs
- safe sanitization, no eval
*/

const fs = require("fs");
const path = require("path");

const HTML_FILE = "opinion.html";
const FEED_FILE = "feed.xml";
const MAX_ITEMS = 500;

function extractJSON(html) {
  if (!html) return null;

  // helper: find balanced {...} starting at given index (skips over strings)
  function extractBalanced(startIdx) {
    let i = startIdx;
    if (html[i] !== '{') return null;
    let depth = 0;
    for (; i < html.length; i++) {
      const ch = html[i];

      // Skip over strings so braces inside strings don't confuse the parser
      if (ch === '"' || ch === "'") {
        const quote = ch;
        i++;
        while (i < html.length) {
          if (html[i] === "\\") {
            i += 2; // skip escaped char
            continue;
          }
          if (html[i] === quote) break;
          i++;
        }
        continue;
      }

      if (ch === "{") depth++;
      else if (ch === "}") {
        depth--;
        if (depth === 0) return html.slice(startIdx, i + 1);
      }
    }
    return null;
  }

  // labels to search for (common patterns used by sites)
  const labels = [
    "initialContents",
    "initial_contents",
    "__INITIAL_STATE__",
    "window.__INITIAL_STATE__",
    "window.initialContents",
    "INITIAL_STATE"
  ];

  for (const label of labels) {
    const idx = html.indexOf(label);
    if (idx === -1) continue;

    // find next '{' after label
    const braceIdx = html.indexOf("{", idx);
    if (braceIdx === -1) continue;

    const raw = extractBalanced(braceIdx);
    if (!raw) continue;

    // sanitize:
    // 1) remove trailing commas before } or ]
    // 2) convert simple single-quoted strings to JSON double-quoted strings
    // 3) remove JS comments (//... and /* ... */)
    let cleaned = raw
      .replace(/\/\*[\s\S]*?\*\//g, "")      // strip block comments
      .replace(/\/\/[^\n\r]*/g, "")          // strip single-line comments
      .replace(/,\s*([}\]])/g, "$1");        // trailing commas

    // convert single-quoted strings to double-quoted strings (simple cases)
    // This attempts to avoid corrupting nested quotes; it's not a full JS->JSON transpiler,
    // but handles the common patterns produced by server-side templating.
    cleaned = cleaned.replace(/'([^'\\]*(\\.[^'\\]*)*)'/g, function (_, inner) {
      // inner is the string contents; JSON.stringify will escape properly
      return JSON.stringify(inner);
    });

    // Attempt JSON.parse; if fails, continue to next label
    try {
      return JSON.parse(cleaned);
    } catch (e) {
      // continue
    }
  }

  // fallback: look for <script type="application/json"> blocks
  const scriptRe = /<script[^>]*type=["']application\/json["'][^>]*>([\s\S]*?)<\/script>/gi;
  let m;
  while ((m = scriptRe.exec(html))) {
    try {
      return JSON.parse(m[1]);
    } catch (e) {}
  }

  // fallback: try to find <script> var data = {...} </script> patterns with balanced extraction
  const genericLabelRe = /<script[^>]*>[\s\S]*?([a-zA-Z0-9_\$]+)\s*[:=]\s*{/gi;
  while ((m = genericLabelRe.exec(html))) {
    const start = html.indexOf("{", m.index);
    if (start === -1) continue;
    const raw = (function () {
      // attempt balanced extraction starting at start
      let i = start, depth = 0;
      for (; i < html.length; i++) {
        if (html[i] === '"' || html[i] === "'") {
          const quote = html[i];
          i++;
          while (i < html.length && html[i] !== quote) {
            if (html[i] === "\\") i++;
            i++;
          }
          continue;
        }
        if (html[i] === "{") depth++;
        else if (html[i] === "}") {
          depth--;
          if (depth === 0) return html.slice(start, i + 1);
        }
      }
      return null;
    })();
    if (!raw) continue;
    let cleaned = raw.replace(/\/\*[\s\S]*?\*\//g, "").replace(/\/\/[^\n\r]*/g, "").replace(/,\s*([}\]])/g, "$1");
    cleaned = cleaned.replace(/'([^'\\]*(\\.[^'\\]*)*)'/g, function (_, inner) { return JSON.stringify(inner); });
    try { return JSON.parse(cleaned); } catch (e) {}
  }

  return null;
}

function loadOldFeedGuids() {
  if (!fs.existsSync(FEED_FILE)) return [];
  try {
    const xml = fs.readFileSync(FEED_FILE, "utf8");
    const match = [...xml.matchAll(/<guid[^>]*>([\s\S]*?)<\/guid>/g)];
    return match.map(m => m[1].trim());
  } catch (e) {
    return [];
  }
}

function xmlEscape(s) {
  if (s === null || s === undefined) return "";
  return String(s)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

function buildRSS(items) {
  const head = `<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
<channel>
<title>DhakaPost Opinion Feed</title>
<link>https://www.dhakapost.com/opinion</link>
<description>Generated</description>
`;
  const tail = `
</channel>
</rss>`;

  const body = items.map(i => `
<item>
  <title><![CDATA[${i.title || ""}]]></title>
  <link>${xmlEscape(i.url || "")}</link>
  <guid>${xmlEscape(i.url || "")}</guid>
  <description><![CDATA[${i.brief || ""}]]></description>
</item>`).join("");

  return head + body + tail;
}

(function main() {
  try {
    if (!fs.existsSync(HTML_FILE)) {
      console.log(`${HTML_FILE} missing`);
      process.exit(0);
    }

    const html = fs.readFileSync(HTML_FILE, "utf8");
    const raw = extractJSON(html) || [];

    // Normalize raw to an array of candidate items
    let dataItems = [];
    if (Array.isArray(raw)) dataItems = raw;
    else if (raw && typeof raw === "object") {
      // common property names
      if (Array.isArray(raw.items)) dataItems = raw.items;
      else if (Array.isArray(raw.contents)) dataItems = raw.contents;
      else if (Array.isArray(raw.articles)) dataItems = raw.articles;
      else {
        // find first array-valued property
        const arrProp = Object.keys(raw).find(k => Array.isArray(raw[k]));
        if (arrProp) dataItems = raw[arrProp];
      }
    }

    // Map and normalize typical fields; be permissive about casing
    const newItems = dataItems
      .map(i => {
        if (!i || typeof i !== "object") return null;
        const url = i.URL || i.url || i.link || i.href || i.path;
        const title = i.Heading || i.title || i.heading || i.name || i.headline;
        const brief = i.Brief || i.brief || i.summary || i.excerpt || i.snippet || "";
        if (!url) return null;
        return { url: String(url).trim(), title: String(title || "").trim(), brief: String(brief || "").trim() };
      })
      .filter(Boolean);

    const oldGuids = loadOldFeedGuids();
    const oldSet = new Set(oldGuids);

    // merge: new items first (excluding duplicates already seen), then append old GUID placeholders
    const merged = [
      ...newItems.filter(i => !oldSet.has(i.url)),
      ...oldGuids.filter(u => !newItems.some(n => n.url === u)).map(u => ({ url: u, title: "", brief: "" }))
    ];

    const finalItems = merged.slice(0, MAX_ITEMS);
    const xml = buildRSS(finalItems);

    fs.writeFileSync(FEED_FILE, xml, "utf8");
    console.log(`Wrote ${FEED_FILE} (${finalItems.length} items)`);
  } catch (err) {
    console.error("extractor error:", err && err.stack ? err.stack : err);
    process.exit(1);
  }
})();