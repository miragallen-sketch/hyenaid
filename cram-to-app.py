#!/usr/bin/env python3
"""
Turn cram-cards.csv into a hyena-id library file you can import straight
into the app.

    pip3 install pillow
    python3 cram-to-app.py cram-cards.csv "KCM North" north-clan.json

It downloads every image, resizes it the same way the app does
(1600px long edge, WebP), groups left and right sides by hyena name,
and writes a library file.

Nothing is guessed silently: anything it cannot parse is listed at the
end and left out of the file.
"""

import csv, io, json, os, re, sys, time, base64, datetime
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError

try:
    from PIL import Image
except ImportError:
    sys.exit("Pillow is missing.  Run:  pip3 install pillow")

MAXPX, QUALITY = 1600, 82

# Cram's category text on the left, the app's folder on the right.
# Add to this if the set uses labels that aren't here.
CLASS_MAP = {
    "cub": "Cubs", "cubs": "Cubs", "c": "Cubs",
    "sub": "Subadults", "subs": "Subadults", "subadult": "Subadults",
    "subadults": "Subadults", "sa": "Subadults",
    "adult female": "Adult Females", "adult females": "Adult Females",
    "af": "Adult Females", "female": "Adult Females", "females": "Adult Females",
    "fem": "Adult Females", "fems": "Adult Females", "f": "Adult Females",
    "adf": "Adult Females",
    "immigrant male": "Immigrant Males", "immigrant males": "Immigrant Males",
    "im": "Immigrant Males", "male": "Immigrant Males", "males": "Immigrant Males",
    "alien": "Aliens", "aliens": "Aliens", "al": "Aliens",
}


# Cram clamps long text, so a label can arrive cut short ("(Su" for "(Sub)").
# Resolve those by prefix, but only when exactly one class matches.
PREFIX_OK = {}

def map_class(raw):
    raw = (raw or "").strip().lower().strip("().,")
    if not raw:
        return None, None
    if raw in CLASS_MAP:
        return CLASS_MAP[raw], None
    hits = {v for k, v in CLASS_MAP.items() if k.startswith(raw)}
    if len(hits) == 1:
        cls = hits.pop()
        PREFIX_OK[raw] = cls
        return cls, f"read {raw!r} as {cls}"
    if len(hits) > 1:
        return None, f"{raw!r} is ambiguous between {', '.join(sorted(hits))}"
    return None, None


def fetch(url, tries=3):
    req = Request(url, headers={"User-Agent": "Mozilla/5.0",
                                "Referer": "https://www.cram.com/"})
    last = None
    for _ in range(tries):
        try:
            with urlopen(req, timeout=45) as r:
                return r.read()
        except (URLError, HTTPError, TimeoutError) as e:
            last = e
            time.sleep(1.5)
    raise last


def shrink(data):
    im = Image.open(io.BytesIO(data))
    im = im.convert("RGB")
    w, h = im.size
    s = min(1.0, MAXPX / max(w, h))
    if s < 1.0:
        im = im.resize((round(w * s), round(h * s)), Image.LANCZOS)
    buf = io.BytesIO()
    im.save(buf, "WEBP", quality=QUALITY, method=5)
    return buf.getvalue(), im.size


def main():
    if len(sys.argv) < 4:
        print(__doc__)
        sys.exit(1)
    src, clan, out = sys.argv[1], sys.argv[2], sys.argv[3]

    with open(src, newline="", encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))
    print(f"{len(rows)} rows in {src}\n")

    animals, skipped, failed = {}, [], []

    for i, r in enumerate(rows, 1):
        name = (r.get("name") or "").strip().upper()
        side = (r.get("side") or "").strip().upper()
        raw_cls = (r.get("class") or "").strip().lower()
        url = (r.get("url") or "").strip()

        if not name or side not in ("L", "R") or not url:
            skipped.append((r.get("raw", ""), "could not read name or side"))
            continue

        cls, note = map_class(raw_cls)
        if cls is None:
            skipped.append((r.get("raw", ""), note or f"unknown class {raw_cls!r}"))
            continue

        try:
            blob, size = shrink(fetch(url))
        except Exception as e:
            failed.append((name, url, str(e)))
            print(f"  [{i}/{len(rows)}] FAILED {name} {side}: {e}")
            continue

        a = animals.setdefault(name, {"cls": cls, "L": [], "R": []})
        if a["cls"] != cls:
            print(f"  ! {name} appears as both {a['cls']} and {cls}; keeping {a['cls']}")
        a[side].append(blob)
        print(f"  [{i}/{len(rows)}] {name} {side}  {size[0]}x{size[1]}  {len(blob)//1024} KB")
        time.sleep(0.2)

    if not animals:
        sys.exit("\nNothing usable was produced.  Check the CSV.")

    hyenas, photos = [], {}
    for name, a in sorted(animals.items()):
        slug = re.sub(r"[^a-z0-9]", "", clan.lower())
        rec = {"id": f"cram-{slug}-{re.sub(r'[^A-Z0-9]', '', name)}",
               "clan": clan, "cls": a["cls"], "name": name,
               "full": "", "sex": "", "dob": "", "mom": "", "ear": "",
               "left": [], "right": []}
        for side, key in (("L", "left"), ("R", "right")):
            for k, blob in enumerate(a[side], 1):
                pid = f"{rec['id']}-{side}{k}"
                photos[pid] = "data:image/webp;base64," + base64.b64encode(blob).decode()
                rec[key].append(pid)
        hyenas.append(rec)

    payload = {"format": "hyena-id-1",
               "exported": datetime.datetime.now(datetime.timezone.utc).isoformat(),
               "clans": [], "hidden": [], "hyenas": hyenas, "photos": photos}
    with open(out, "w") as f:
        json.dump(payload, f)

    mb = os.path.getsize(out) / 1048576
    print(f"\n{'='*52}")
    print(f"{len(hyenas)} hyenas, {len(photos)} photos → {out}  ({mb:.1f} MB)")

    from collections import Counter
    for c, n in sorted(Counter(h["cls"] for h in hyenas).items()):
        print(f"   {c:<16} {n}")

    if PREFIX_OK:
        print("\nTruncated labels I resolved by prefix — check these are right:")
        for k, v in sorted(PREFIX_OK.items()):
            print(f"   {k!r} -> {v}")

    lonely = [h["name"] for h in hyenas if not h["left"] or not h["right"]]
    if lonely:
        print(f"\n{len(lonely)} with only one side: {', '.join(lonely[:20])}"
              + (" ..." if len(lonely) > 20 else ""))
    if skipped:
        print(f"\n{len(skipped)} rows skipped:")
        for raw, why in skipped[:20]:
            print(f"   {why}: {raw!r}")
        if len(skipped) > 20:
            print(f"   ... and {len(skipped)-20} more")
    if failed:
        print(f"\n{len(failed)} downloads failed:")
        for n, u, e in failed[:10]:
            print(f"   {n}: {e}")


if __name__ == "__main__":
    main()
