// robust extractJSON: finds a JS object after common labels and parses it
function extractJSON(html) {
  if (!html) return null;

  // helper: find balanced {...} starting at first '{' after an index
  function extractBalanced(startIdx) {
    let i = startIdx;
    if (html[i] !== '{') return null;
    let depth = 0;
    for (; i < html.length; i++) {
      const ch = html[i];
      if (ch === '{') depth++;
      else if (ch === '}') {
        depth--;
        if (depth === 0) return html.slice(startIdx, i + 1);
      }
      // skip over strings to avoid miscounting braces inside them
      if (ch === '"' || ch === "'") {
        const quote = ch;
        i++;
        while (i < html.length && html[i] !== quote) {
          if (html[i] === '\\') i++; // skip escaped char
          i++;
        }
      }
    }
    return null;
  }

  // try a label and balanced-brace extraction
  const labels = [
    'initialContents',
    'initial_contents',
    '__INITIAL_STATE__',
    'window.__INITIAL_STATE__',
    'window.initialContents'
  ];

  for (const label of labels) {
    const idx = html.indexOf(label);
    if (idx === -1) continue;
    // look forward for first '{'
    const braceIdx = html.indexOf('{', idx);
    if (braceIdx === -1) continue;
    const raw = extractBalanced(braceIdx);
    if (!raw) continue;

    // sanitize: remove trailing commas before } or ]
    let cleaned = raw.replace(/,\s*([}\]])/g, '$1');

    // convert single-quoted strings to double-quoted when safe-ish
    // only convert simple cases: '...'
    cleaned = cleaned.replace(/'([^'\\]*(\\.[^'\\]*)*)'/g, function(_, inner) {
      return JSON.stringify(inner);
    });

    // attempt JSON.parse
    try {
      return JSON.parse(cleaned);
    } catch (e) {
      // fall through to next label
    }
  }

  // fallback: try to find a pure JSON <script type="application/json"> block
  const scriptRe = /<script[^>]*type=["']application\/json["'][^>]*>([\s\S]*?)<\/script>/gi;
  let m;
  while ((m = scriptRe.exec(html))) {
    try {
      return JSON.parse(m[1]);
    } catch (e) {}
  }

  return null;
}