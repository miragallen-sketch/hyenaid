#!/usr/bin/env python3
"""
Turn a sorted photo bank into hyena-id library files.

Expects the tree you already have:

    bank/
      Talek West/
        Adult Females/
          BIND/
            BIND R 1039.jpg
            BIND L 04.jpg
            BIND playing.jpg      <- skipped, no L/R token
        Cubs/
          ...
      KCM North/
      Serena North/

Clan and class are read from the folder names, so nothing needs typing.

  LOOK FIRST, change nothing:

      python3 bank-to-app.py scan /path/to/bank

  THEN BUILD one library file per clan:

      python3 bank-to-app.py build /path/to/bank out/

An ID photo is any filename containing a standalone L or R token,
optionally followed by a number:
      BIND R 1039  ->  right, group 1
      BIND R2 321  ->  right, group 2
Everything else in the folder is treated as a fun photo and left out.
"""

import io, json, os, re, sys, base64, datetime
from collections import defaultdict, Counter

try:
    from PIL import Image
except ImportError:
    sys.exit("Pillow is missing.  Run:  pip install pillow")

try:
    import pillow_heif
    pillow_heif.register_heif_opener()
except ImportError:
    pass

MAXPX, QUALITY = 1600, 82
EXTS = {".jpg", ".jpeg", ".png", ".webp", ".tif", ".tiff", ".heic", ".heif"}

APP_CLANS = ["Talek West", "KCM North", "KCM South",
             "Serena North", "Serena South", "Happy Zebra"]

# Folder name (lowercased) -> app folder.
CLASS_MAP = {
    "cubs": "Cubs", "cub": "Cubs",
    "subs": "Subadults", "sub": "Subadults", "subadults": "Subadults",
    "subadult": "Subadults", "sa": "Subadults",
    "adult females": "Adult Females", "adult female": "Adult Females",
    "females": "Adult Females", "female": "Adult Females",
    "af": "Adult Females", "fem": "Adult Females", "fems": "Adult Females",
    # your bank says "Adult Males"; the app folder is "Immigrant Males"
    "adult males": "Immigrant Males", "adult male": "Immigrant Males",
    "immigrant males": "Immigrant Males", "immigrant male": "Immigrant Males",
    "males": "Immigrant Males", "male": "Immigrant Males",
    "im": "Immigrant Males", "am": "Immigrant Males",
    "aliens": "Aliens", "alien": "Aliens", "al": "Aliens",
}

SKIP_DIR = re.compile(r"^(missing|unid|un-?id|unknown|unidentified|"
                      r"archive|old|dup(licate)?s?|trash|misc)$", re.I)

SIDE_TOKEN = re.compile(r"^([LR])(\d*)$", re.I)


def match_clan(part):
    p = part.strip().lower()
    for c in APP_CLANS:
        if p == c.lower() or p.replace(" ", "") == c.lower().replace(" ", ""):
            return c
    return None


def parse_side(fname):
    """(side, group) or None."""
    stem = os.path.splitext(fname)[0]
    for t in re.split(r"[\s_\-]+", stem):
        m = SIDE_TOKEN.match(t)
        if m:
            return m.group(1).upper(), int(m.group(2) or 1)
    return None


def walk(root):
    """-> (records, skipped_files, unplaced_folders)"""
    recs, skipped, unknown = [], [], Counter()
    root = os.path.abspath(root)

    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames
                       if not d.startswith(".") and not SKIP_DIR.match(d)]
        rel = os.path.relpath(dirpath, root)
        parts = [] if rel == "." else rel.split(os.sep)

        clan = cls = None
        cls_at = -1
        for i, p in enumerate(parts):
            c = match_clan(p)
            if c and clan is None:
                clan = c
            k = CLASS_MAP.get(p.strip().lower())
            if k and cls is None:
                cls, cls_at = k, i

        # The hyena's own folder is whatever sits below the class folder.
        name_from_dir = ""
        if cls_at >= 0 and len(parts) > cls_at + 1:
            name_from_dir = parts[-1].strip().upper()

        imgs = [f for f in sorted(filenames)
                if not f.startswith(".") and os.path.splitext(f)[1].lower() in EXTS]
        if not imgs:
            continue

        if clan is None or cls is None:
            unknown[rel] += len(imgs)
            continue

        for fn in imgs:
            path = os.path.join(dirpath, fn)
            sd = parse_side(fn)
            if not sd:
                skipped.append(path)
                continue
            stem = os.path.splitext(fn)[0]
            before = re.split(r"[\s_\-]+", stem)[0].upper()
            name = name_from_dir or before
            if not name:
                skipped.append(path)
                continue
            recs.append(dict(clan=clan, cls=cls, name=name,
                             side=sd[0], group=sd[1], path=path))
    return recs, skipped, unknown


def cmd_scan(root):
    recs, skipped, unknown = walk(root)
    if not recs:
        sys.exit("No ID photos found. Check the path and the folder names.")

    tree = defaultdict(lambda: defaultdict(lambda: {"L": 0, "R": 0}))
    for r in recs:
        tree[r["clan"]][(r["cls"], r["name"])][r["side"]] += 1

    total = 0
    for clan in sorted(tree, key=lambda c: APP_CLANS.index(c)):
        rows = tree[clan]
        print(f"\n{'='*46}\n{clan}   {len(rows)} hyenas")
        by_cls = defaultdict(list)
        for (cls, name), v in rows.items():
            by_cls[cls].append((name, v))
        for cls in sorted(by_cls):
            print(f"\n  {cls}  ({len(by_cls[cls])})")
            for name, v in sorted(by_cls[cls]):
                flag = "" if v["L"] and v["R"] else "   <- one side only"
                print(f"     {name:<14} L{v['L']}  R{v['R']}{flag}")
                total += v["L"] + v["R"]

    print(f"\n{'='*46}\n{total} ID photos across {len(tree)} clans")
    print(f"{len(skipped)} files skipped as not-an-ID-photo")
    for p in skipped[:12]:
        print("   ", os.path.relpath(p, root))
    if len(skipped) > 12:
        print(f"    ... and {len(skipped)-12} more")
    print("\nRead that list. Anything there that IS a left or right photo means "
          "the naming pattern needs widening.")

    if unknown:
        print(f"\nFolders I could not place ({sum(unknown.values())} photos):")
        for k, n in unknown.most_common(12):
            print(f"   {k}  ({n} photos)")
        print("Tell me the folder names and I will map them.")


def shrink(path):
    im = Image.open(path).convert("RGB")
    w, h = im.size
    s = min(1.0, MAXPX / max(w, h))
    if s < 1.0:
        im = im.resize((round(w * s), round(h * s)), Image.LANCZOS)
    buf = io.BytesIO()
    im.save(buf, "WEBP", quality=QUALITY, method=5)
    return buf.getvalue(), im.size


def cmd_build(root, outdir):
    recs, skipped, unknown = walk(root)
    if not recs:
        sys.exit("No ID photos found.")
    os.makedirs(outdir, exist_ok=True)

    per_clan = defaultdict(lambda: defaultdict(lambda: {"L": [], "R": []}))
    for r in recs:
        per_clan[r["clan"]][(r["cls"], r["name"])][r["side"]].append((r["group"], r["path"]))

    failed = []
    for clan in sorted(per_clan, key=lambda c: APP_CLANS.index(c)):
        slug = re.sub(r"[^a-z0-9]", "", clan.lower())
        hyenas, photos = [], {}
        print(f"\n=== {clan} ===")
        for (cls, name) in sorted(per_clan[clan]):
            a = per_clan[clan][(cls, name)]
            rec = {"id": f"bank-{slug}-{re.sub(r'[^A-Z0-9]', '', name)}",
                   "clan": clan, "cls": cls, "name": name,
                   "full": "", "sex": "", "dob": "", "mom": "", "ear": "",
                   "left": [], "right": []}
            for side, key in (("L", "left"), ("R", "right")):
                for k, (grp, path) in enumerate(sorted(a[side]), 1):
                    try:
                        blob, size = shrink(path)
                    except Exception as e:
                        failed.append((os.path.basename(path), str(e)))
                        continue
                    pid = f"{rec['id']}-{side}{k}"
                    photos[pid] = "data:image/webp;base64," + base64.b64encode(blob).decode()
                    rec[key].append(pid)
            if rec["left"] or rec["right"]:
                hyenas.append(rec)
                print(f"  {name:<14}{cls:<16}L{len(rec['left'])} R{len(rec['right'])}")

        out = os.path.join(outdir, slug + ".json")
        with open(out, "w") as f:
            json.dump({"format": "hyena-id-1",
                       "exported": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                       "clans": [], "hidden": [], "hyenas": hyenas, "photos": photos}, f)
        mb = os.path.getsize(out) / 1048576
        print(f"  -> {out}  {len(hyenas)} hyenas, {len(photos)} photos, {mb:.1f} MB")
        if mb > 150:
            print("     Large file. Import on a laptop, not a phone.")

    if failed:
        print(f"\n{len(failed)} files could not be read:")
        for fn, e in failed[:10]:
            print(f"   {fn}: {e}")
        if any(fn.lower().endswith(("heic", "heif")) for fn, _ in failed):
            print("   For iPhone photos:  pip install pillow-heif")
    if unknown:
        print(f"\nLeft out, folders I could not place: {sum(unknown.values())} photos")
        for k, n in unknown.most_common(8):
            print(f"   {k}  ({n})")


if __name__ == "__main__":
    if len(sys.argv) >= 3 and sys.argv[1] == "scan":
        cmd_scan(sys.argv[2])
    elif len(sys.argv) >= 4 and sys.argv[1] == "build":
        cmd_build(sys.argv[2], sys.argv[3])
    else:
        print(__doc__)
        sys.exit(1)
