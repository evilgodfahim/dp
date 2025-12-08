import fs from "fs";

const HTML_FILE = "opinion.html";
const FEED_FILE = "feed.xml";
const MAX_ITEMS = 500;

function extractJSON(html) {
  const key = "\"initialContents\"";
  const pos = html.indexOf(key);
  if (pos === -1) return null;

  let i = pos;
  while (i >= 0 && html[i] !== "{") i--;
  let start = i;

  let depth = 0;
  let end = -1;
  for (let j = start; j < html.length; j++) {
    if (html[j] === "{") depth++;
    if (html[j] === "}") depth--;
    if (depth === 0) {
      end = j + 1;
      break;
    }
  }
  if (end === -1) return null;

  const jsonText = html.slice(start, end);
  return JSON.parse(jsonText).initialContents;
}

function loadOldFeed() {
  if (!fs.existsSync(FEED_FILE)) return [];

  const xml = fs.readFileSync(FEED_FILE, "utf8");
  const match = [...xml.matchAll(/<guid>(.*?)<\/guid>/g)];
  return match.map(m => m[1]);
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
<title><![CDATA[${i.title}]]></title>
<link>${i.url}</link>
<guid>${i.url}</guid>
<description><![CDATA[${i.brief || ""}]]></description>
</item>`).join("");

  return head + body + tail;
}

function xmlEscape(s) {
  return s.replace(/&/g, "&amp;").replace(/</g, "&lt;");
}

(function main() {
  if (!fs.existsSync(HTML_FILE)) {
    console.log("opinion.html missing");
    process.exit(0);
  }

  const html = fs.readFileSync(HTML_FILE, "utf8");
  const data = extractJSON(html) || [];

  const newItems = data.map(i => ({
    url: i.URL,
    title: i.Heading,
    brief: i.Brief
  }));

  // old GUIDs
  const oldUrls = new Set(loadOldFeed());

  const merged = [
    ...newItems.filter(i => !oldUrls.has(i.url)),
    ...Array.from(oldUrls).map(u => ({ url: u, title: "", brief: "" }))
  ];

  const finalItems = merged.slice(0, MAX_ITEMS);
  const xml = buildRSS(finalItems);

  fs.writeFileSync(FEED_FILE, xml);
})();