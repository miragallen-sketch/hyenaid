# Hyena ID

A phone and tablet replacement for the ID binders. Left photo on top, right photo on
bottom, with text you type yourself overlaid. Works with no signal once installed.

Current build: **2026-07-19x**

## Files

| File | What it is | Changes? |
|---|---|---|
| `index.html` | The whole app | Every build |
| `sw.js` | Offline cache. Its version number is what forces phones to pick up a new build | Every build |
| `manifest.json` | App name, colours, icon list | Rarely |
| `icon-192.png`, `icon-512.png`, `icon-maskable-512.png`, `apple-touch-icon.png` | Home screen icons | Rarely |
| `README.md` | This file | Not part of the app |

Upload everything if you'd rather not track which files changed.

## Putting it online

1. New GitHub repo, e.g. `mara-hyena-project/hyena-id`.
2. Drag the files in through the web page. No git needed.
3. Settings → Pages → Deploy from branch → `main` / root.
4. Open `https://<org>.github.io/hyena-id/` on a phone.

**Install it.** iPhone: Share → Add to Home Screen. Android: menu → Install app.
It needs to be on the home screen to run full screen and to hold its photos reliably.

### When an update doesn't appear

Check the build number at the bottom of the Library screen. If it isn't the one you
just uploaded:

1. Library → **Reload the latest app version**. Keeps all hyenas and photos.
2. Still stale? The new files probably aren't on the server. Load
   `https://<your-site>/index.html` directly and check.
3. For the icon specifically, delete the home screen shortcut and re-add it. iOS caches
   icons separately and ignores everything else.

## Using it

**Browse.** Pick a clan, pick an age–sex class, then:

| Gesture | Does |
|---|---|
| swipe up / down | next or previous hyena |
| swipe left / right | other photos of the same hyena, different angle or light |
| tap a photo | full screen; pinch to zoom, drag to pan, double-tap for 2.5x, X to close |
| eye icon, top bar | hide or show the text |

Arrow keys, space and Escape do the same on a laptop, where the scroll wheel zooms.

**Add a hyena.** `+` from the class list. Type whatever you want overlaid; none of it is
checked or connected to any database. Photos are shrunk to 1600px on the device, so
full-size camera files are fine to hand it.

**Set the default photo.** In the edit screen, tap a photo to move it to first position.
First is what you land on; the rest are the sideways swipes.

**Move between folders.** Edit the hyena, change the Clan or Class dropdown, save.
Photos follow.

**Crop.** Tap a photo, then the crop icon. Drag the corners, then Crop.
**This replaces the photo permanently.** There's no undo. The originals live in the
photo bank and on personal laptops, so the app is not the archive.

## Clans

Six built in: Talek West, KCM North, KCM South, Serena North, Serena South, Happy Zebra.
Every clan has the same five classes: Cubs, Subadults, Adult Females, Immigrant Males,
Aliens.

Library → Clans to manage them:

- **Add a clan** from the bottom of the clan list. It gets the same five classes.
- **Hide** takes a clan out of daily use but keeps everything. This is what to use for a
  dropped study clan. "Show" brings it back.
- **Delete** only appears once a clan is hidden, and asks you to type the clan name if it
  still holds hyenas.

Hidden status travels in export files. Importing a library containing hyenas from a
hidden clan un-hides it, on the principle that arriving photos shouldn't vanish silently.

## Camp sync

If a Cloudflare Worker has been set up (see `hyena-sync/SETUP.md`), Library → Camp sync
holds a server address and a shared camp password. Press **Sync now** and the device
sends its changes and collects everyone else's.

This is the better route once several people are adding hyenas. Only what changed moves,
nothing large is ever held in memory, and a new RA gets the whole library with one
button. Deletions propagate, which exports alone cannot do.

The app works fine without it. Leave the fields blank and use exports.

## Sharing between devices, without a server

Each device holds its own library. Library → Export writes a file; Library → Import reads
one on another device.

Large clans are split into numbered parts automatically, since a browser cannot build one
enormous file. Save each part, then import all of them on the other device; order does not
matter.

**Export one clan at a time**, or one class within a clan. The whole library in a single
file is more than a browser can build. The size estimate under the dropdowns updates as
you choose, and warns you when a selection is too big.

Importing merges: photo lists are unioned, so two RAs adding photos of the same hyena in
the same week won't overwrite each other. Text fields are last-writer-wins. Hyenas are
matched by name within a clan, so moving one between classes propagates rather than
duplicating.

Over camp WiFi, a shared Google Drive or Dropbox folder is the practical channel. Email
caps out around 25 MB and these files are far bigger.

## Bulk imports

Two scripts turn existing collections into importable library files. Both need Python
with Pillow:

```
python3 -m venv venv
source venv/bin/activate
pip install pillow
```

**From a Cram set** — `cram-scrape.js` in the browser console on the set page (scroll to
the bottom first so every card loads), then:

```
python3 cram-to-app.py cram-cards.csv "Serena North" serena-north.json
```

**From a sorted photo bank** — clan and class are read from the folder names:

```
python3 bank-to-app.py scan  /path/to/bank        # look, change nothing
python3 bank-to-app.py build /path/to/bank out/   # one file per clan
```

An ID photo is any filename holding a standalone `L` or `R` token, optionally numbered:
`BIND R 1039`, `BIND R2 321`. Everything else is treated as a fun photo and left out.
Folders named `missing`, `unID`, `unknown`, `old` and similar are skipped.

Read the scan output before building. It lists what it skipped, which is where mistakes
will be.

Import bulk files on a **laptop**, not a phone, then export per clan to the phones.

## Known limits

- Storage is per device and per browser. Clearing site data erases the library. Export
  after any big session and keep the file somewhere backed up.
- iOS can evict data from a site left unopened for weeks. Home screen installation makes
  this much less likely, but keep the export.
- Re-importing a bulk file replaces cropped photos with the uncropped originals. Do the
  bulk imports first, crop afterwards.
- High-ISO photos compress badly. Budget 300–700 KB each.
- Zoom goes to 6x but photos are stored at 1600px, so past 2–3x you're looking at
  interpolated pixels rather than more detail.
