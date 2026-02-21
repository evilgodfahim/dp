// extractor.js
const fs = require("fs");
const path = require("path");

const HTML_FILE = "opinion.html";
const FEED_FILE = "feed.xml";
const MAX_ITEMS = 500;

function extractJSON(html) {
  if (!html) return null;

  // Try to extract a JSON object that contains "initialContents"
  const re1 = /initialContents\s*[:=]\s*(\{[\s\S]*?\})/m;
  let m = html.match(re1);
  if (m) {
    try {
      const parsed = JSON.parse(m[1]);
      if (parsed && (parsed.initialContents || Object.keys(parsed).length)) {
        return parsed.initialContents || parsed;
      }
    } catch (e) {}
  }

  // Fallback: try common window-initial-state patterns
  const re2 = /window\.__INITIAL_STATE__\s*=\s*(\{[\s\S]*?\});/m;
  m = html.match(re2);
  if (m) {
    try { return JSON.parse(m[1]); } catch (e) {}
  }

  // Fallback: look for a JSON script tag
  const reScript = /<script[^>]*>\s*({\s*"initialContents"[\s\S]*?})\s*<\/script>/m;
  m = html.match(reScript);
  if (m) {
    try {
      const parsed = JSON.parse(m[1]);
      return parsed.initialContents || parsed;
    } catch (e) {}
  }

  return null;
}

function loadOldFeedGuids() {
  if (!fs.existsSync(FEED_FILE)) return [];
  const xml = fs.readFileSync(FEED_FILE, "utf8");
  const match = [...xml.matchAll(/<guid[^>]*>([\s\S]*?)<\/guid>/g)];
  return match.map(m => m[1].trim());
}

function xmlEscape(s) {
  if (!s && s !== 0) return "";
  return String(s)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
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
  if (!fs.existsSync(HTML_FILE)) {
    console.log("opinion.html missing");
    process.exit(0);
  }

  const html = fs.readFileSync(HTML_FILE, "utf8");
  const raw = extractJSON(html) || [];

  // raw might be an object; try to normalize to an array of items
  let dataItems = [];
  if (Array.isArray(raw)) {
    dataItems = raw;
  } else if (raw && typeof raw === "object") {
    // Common keys to look for
    if (Array.isArray(raw.items)) dataItems = raw.items;
    else if (Array.isArray(raw.contents)) dataItems = raw.contents;
    else {
      // attempt to find the first array-valued property
      const arrProp = Object.keys(raw).find(k => Array.isArray(raw[k]));
      if (arrProp) dataItems = raw[arrProp];
    }
  }

  // Normalize fields and filter invalid entries
  const newItems = dataItems
    .map(i => {
      if (!i || typeof i !== "object") return null;
      const url = i.URL || i.url || i.link || i.href;
      const title = i.Heading || i.title || i.heading || i.name;
      const brief = i.Brief || i.brief || i.summary || i.excerpt || "";
      if (!url) return null;
      return { url: String(url).trim(), title: String(title || "").trim(), brief: String(brief || "").trim() };
    })
    .filter(Boolean);

  // old GUIDs (urls)
  const oldGuids = loadOldFeedGuids();
  const oldSet = new Set(oldGuids);

  // merge: keep new items first, then keep previous GUID placeholders (to preserve order/history)
  const merged = [
    ...newItems.filter(i => !oldSet.has(i.url)),
    ...oldGuids.filter(u => !newItems.some(n => n.url === u)).map(u => ({ url: u, title: "", brief: "" }))
  ];

  const finalItems = merged.slice(0, MAX_ITEMS);
  const xml = buildRSS(finalItems);

  fs.writeFileSync(FEED_FILE, xml, "utf8");
  console.log(`Wrote ${FEED_FILE} (${finalItems.length} items)`);
})();