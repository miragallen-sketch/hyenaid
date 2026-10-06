/* Cram → CSV.  v2, written against the real markup.
   Open the set, scroll to the very bottom so every card loads,
   then paste this whole block into the console. */
(function () {
  const CHROME = /^(term|definition|front|back|hint|click to enlarge|flashcard image|no text to read on this side)$/i;

  // Largest URL in a srcset, falling back to src.
  function best(img) {
    const ss = img.getAttribute("srcset");
    if (ss) {
      const cands = ss.split(",").map(p => {
        const [u, w] = p.trim().split(/\s+/);
        return { u, w: parseInt(w) || 0 };
      }).sort((a, b) => b.w - a.w);
      if (cands.length && cands[0].u) return cands[0].u;
    }
    return img.currentSrc || img.src;
  }

  // Nearest ancestor that actually carries the card's text.
  function rowText(img) {
    let n = img, up = 0;
    while (n.parentElement && up < 8) {
      n = n.parentElement; up++;
      let t = (n.innerText || "").replace(/\s+/g, " ").trim();
      if (!t) continue;
      t = t.split("\n").map(x => x.trim()).filter(x => x && !CHROME.test(x)).join(" ").trim();
      if (t && !CHROME.test(t)) return t;
    }
    return "";
  }

  const imgs = [...document.querySelectorAll("img")]
    .filter(i => /assets\.cram\.com/.test(i.currentSrc || i.src || i.getAttribute("srcset") || ""));

  const byUrl = new Map();
  imgs.forEach(im => {
    const url = best(im);
    const txt = rowText(im);
    const prev = byUrl.get(url);
    // Keep whichever occurrence produced real text — drops the study-view duplicate.
    if (!prev || (txt && txt.length > prev.length)) byUrl.set(url, txt);
  });

  const rows = [...byUrl.entries()].map(([url, text], i) => {
    // "ANIM R (Cub)"  /  "ANIM L Cub"  /  "ANIM R"
    const m = text.match(/^(.*?)[\s,]+([LR])\b[\s,]*\(?\s*([^)]*?)\s*\)?$/i);
    return {
      n: i + 1,
      raw: text,
      name: m ? m[1].trim() : text,
      side: m ? m[2].toUpperCase() : "",
      cls:  m ? (m[3] || "").trim() : "",
      url:  url.startsWith("//") ? location.protocol + url : url
    };
  });

  const bad = rows.filter(r => !r.side || !r.name);
  console.table(rows.slice(0, 25));
  console.log("images:", rows.length, "| unparsed:", bad.length);
  if (bad.length) { console.warn("Rows I could not split into name/side:"); console.table(bad.slice(0, 15)); }

  const esc = v => '"' + String(v).replace(/"/g, '""') + '"';
  const csv = "n,name,side,class,raw,url\n" + rows.map(r =>
    [r.n, esc(r.name), r.side, esc(r.cls), esc(r.raw), esc(r.url)].join(",")).join("\n");

  const a = document.createElement("a");
  a.href = URL.createObjectURL(new Blob([csv], { type: "text/csv" }));
  a.download = "cram-cards.csv";
  a.click();
  console.log("%cSaved cram-cards.csv", "color:#e8b23a;font-weight:bold");
})();
