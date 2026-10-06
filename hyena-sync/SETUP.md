# Camp sync setup

One Cloudflare Worker plus one R2 bucket. Free at your size: R2 gives 10 GB of storage
with no charge for downloads, and Workers allow 100,000 requests a day. The library is
about 660 MB.

You only do this once. After that, RAs type an address and a password into the app and
press Sync.

## What you need

- A Cloudflare account (free). R2 asks for a card on file even on the free tier.
- Node.js on your laptop. Check with `node --version`; if that fails, install from
  nodejs.org.
- `worker.js` and `wrangler.toml` from this folder.

## 1. Log in

```
cd hyena-sync
npx wrangler login
```

A browser window opens. Approve it.

## 2. Make the bucket

```
npx wrangler r2 bucket create hyena-id
```

The name must match `bucket_name` in `wrangler.toml`.

## 3. Set the camp password

```
npx wrangler secret put SYNC_KEY
```

It prompts you; type the password and press Enter. It is never written to a file and
never appears in the repo. Pick something you're willing to give to every RA — this is
about keeping strangers out, not about tracking who did what.

## 4. Deploy

```
npx wrangler deploy
```

It prints a URL like:

```
https://hyena-sync.yourname.workers.dev
```

That's the server address. Check it works:

```
curl https://hyena-sync.yourname.workers.dev/api/ping
```

You should see `{"ok":true}`.

## 5. Connect the app

On each device: Library → Camp sync → paste the address and password → **Sync now**.

Do your laptop first, since it holds the full library. The first sync uploads everything,
so leave it on camp WiFi and let it run. After that, syncs only move what changed.

Then on the phones: same address and password, press Sync, and the whole library comes
down. A new RA is one button rather than eighteen files.

## What sync does

1. Collects any records the server has that are newer than yours.
2. Sends any records of yours the server hasn't seen, uploading the photos first.
3. Downloads any photo you're missing.

Nothing is ever held in memory beyond one photo at a time, which is why this works on a
phone where exporting a whole clan did not.

Conflicts resolve by whoever edited last. Photo lists are per-record, so two RAs adding
photos to different hyenas never interact at all. Two people editing the *same* hyena in
the same minute is the only case where one edit wins, and that was true of the file
method too.

**Deletions now propagate.** Deleting a hyena leaves a marker that tells other devices to
drop it. Under the old file method a deleted hyena came back at the next import.

**Cropping makes a new photo id**, so other devices see the cropped version rather than
keeping the original silently.

## Checking on it

```
curl -H "Authorization: Bearer YOUR-PASSWORD" \
     https://hyena-sync.yourname.workers.dev/api/stat
```

Returns live hyenas, deletion markers, photo count and total bytes.

The Cloudflare dashboard shows requests and storage under Workers and R2.

## Clearing out deleted photos

Deleting a photo in the app updates the hyena's record, and that syncs. But the photo
file itself stays on the server forever — nothing removes it. After a big pruning
session the server still holds everything, and still lists it all at every sync.

`cleanup.sh` fixes that:

```
cd hyena-sync
./cleanup.sh
```

It shows the current counts, asks for confirmation, deletes photos no hyena points at,
and shows the counts again.

**Run it only after every device has synced.** The server acts on the records it has
received. If an RA has deleted nothing but simply hasn't synced in a while, their photos
are still referenced and safe. The danger is the reverse: someone who added photos and
hasn't pushed them yet has nothing on the server to protect, so there is nothing to
delete either. In practice the rule is simply: have everyone sync, then clean.

This is deliberately not a button in the app. It needs doing a few times a year, and it
is the one operation that can remove other people's work if run at the wrong moment.

## Backups

R2 is not a backup — it's the shared copy. If someone deletes a clan, the deletion syncs
everywhere, which is the point but also the risk.

Keep doing occasional per-clan exports and put them somewhere durable. Monthly is plenty.
The photo bank on the laptops remains the real archive.

## Cost, honestly

At 660 MB and a handful of people syncing daily you will not pay anything. The free tier
covers 10 GB stored and 1 million writes a month. You'd need to roughly fifteen times the
library before storage costs appear, and then it's cents.

Watch one thing: every sync lists what photos the server has. That's one request per 400
photos, so a full sync from a fresh phone is a few thousand requests. Fine against a
100,000 a day allowance, but if you ever have twenty RAs all syncing repeatedly, check
the dashboard.

## If it breaks

**"Password rejected"** — the password in the app doesn't match `SYNC_KEY`. Re-run
`npx wrangler secret put SYNC_KEY` to set it again.

**"Server said 500"** — check the logs with `npx wrangler tail` while someone syncs.

**"Sync failed" with nothing else** — usually no connectivity. The app keeps working
offline; sync when there's signal.

**A sync that stops partway** — safe to press Sync again. It picks up what's missing
rather than starting over.

## Turning it off

The app works without sync. Leave the fields blank and use exports as before. Deleting
the Worker and bucket removes the server; the phones keep their libraries.
