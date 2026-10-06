/**
 * Hyena ID sync server — a single Cloudflare Worker backed by an R2 bucket.
 *
 * Bindings expected (see wrangler.toml):
 *   BUCKET    R2 bucket
 *   SYNC_KEY  secret, the shared camp password
 *
 * Layout inside the bucket:
 *   index.json      every hyena record, keyed by id
 *   photo/<id>      one WebP per photo
 *
 * Endpoints (all POST/GET under /api):
 *   GET  /api/index          -> {ts, records:{id:rec}}
 *   POST /api/push           {records:[...]}  -> merges, last edit wins
 *   POST /api/have           {ids:[...]}      -> {missing:[...]}
 *   PUT  /api/photo/<id>     raw bytes
 *   GET  /api/photo/<id>     raw bytes
 *   GET  /api/stat           -> {hyenas, photos, bytes}
 */

const VERSION = "2026-07-19x";

const CORS = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Methods": "GET,PUT,POST,OPTIONS",
  "Access-Control-Allow-Headers": "Authorization,Content-Type",
  "Access-Control-Max-Age": "86400",
};

const json = (obj, status = 200) =>
  new Response(JSON.stringify(obj), {
    status,
    headers: { ...CORS, "Content-Type": "application/json" },
  });

function authed(req, env) {
  const h = req.headers.get("Authorization") || "";
  const tok = h.startsWith("Bearer ") ? h.slice(7) : "";
  if (!env.SYNC_KEY) return false;
  // constant-time-ish compare
  if (tok.length !== env.SYNC_KEY.length) return false;
  let diff = 0;
  for (let i = 0; i < tok.length; i++) diff |= tok.charCodeAt(i) ^ env.SYNC_KEY.charCodeAt(i);
  return diff === 0;
}

async function readIndex(env) {
  const obj = await env.BUCKET.get("index.json");
  if (!obj) return { records: {}, etag: null };
  try {
    return { records: JSON.parse(await obj.text()), etag: obj.etag };
  } catch {
    return { records: {}, etag: obj.etag };
  }
}

/* Merge incoming records into index.json.  R2 conditional writes let us
   detect another device having written in between, so a simultaneous sync
   from two phones cannot silently drop one side's edits. */
async function mergePush(env, incoming) {
  for (let attempt = 0; attempt < 6; attempt++) {
    const { records, etag } = await readIndex(env);
    let changed = 0;
    for (const rec of incoming) {
      if (!rec || !rec.id) continue;
      const cur = records[rec.id];
      if (!cur || (rec.mod || 0) >= (cur.mod || 0)) {
        records[rec.id] = rec;
        changed++;
      }
    }
    const body = JSON.stringify(records);
    let wrote = null;
    try {
      wrote = await env.BUCKET.put("index.json", body, {
        httpMetadata: { contentType: "application/json" },
        onlyIf: etag ? { etagMatches: etag } : { etagDoesNotMatch: "*" },
      });
    } catch (e) {
      wrote = null;
    }
    // null means another device wrote first: re-read and merge again
    if (wrote) return { ok: true, changed, count: Object.keys(records).length };
    await new Promise(r => setTimeout(r, 40 + Math.random() * 120 * (attempt + 1)));
  }
  return { ok: false, error: "index busy, try again" };
}

export default {
  async fetch(req, env) {
    if (req.method === "OPTIONS") return new Response(null, { headers: CORS });

    const url = new URL(req.url);
    const path = url.pathname.replace(/\/+$/, "");

    // no password needed: lets you confirm which code is deployed
    if (path === "/api/ping") {
      return json({
        ok: true,
        version: VERSION,
        endpoints: ["/api/index", "/api/push", "/api/photos", "/api/have",
                    "/api/photo/<id>", "/api/gc", "/api/stat"],
      });
    }

    if (!authed(req, env)) return json({ error: "bad password" }, 401);

    try {
      if (path === "/api/index" && req.method === "GET") {
        const { records } = await readIndex(env);
        return json({ ts: Date.now(), records });
      }

      if (path === "/api/push" && req.method === "POST") {
        const { records } = await req.json();
        if (!Array.isArray(records)) return json({ error: "records must be a list" }, 400);
        return json(await mergePush(env, records));
      }

      /* One listing beats thousands of individual lookups and stays well
         inside the per-request subrequest limit. */
      if (path === "/api/photos" && req.method === "GET") {
        const ids = [];
        let cursor;
        do {
          const list = await env.BUCKET.list({ prefix: "photo/", cursor, limit: 1000 });
          for (const o of list.objects) ids.push(o.key.slice(6));
          cursor = list.truncated ? list.cursor : null;
        } while (cursor);
        return json({ ids });
      }

      if (path === "/api/have" && req.method === "POST") {
        const { ids } = await req.json();
        if (!Array.isArray(ids)) return json({ error: "ids must be a list" }, 400);
        const have = new Set();
        let cursor;
        do {
          const list = await env.BUCKET.list({ prefix: "photo/", cursor, limit: 1000 });
          for (const o of list.objects) have.add(o.key.slice(6));
          cursor = list.truncated ? list.cursor : null;
        } while (cursor);
        return json({ missing: ids.filter(id => !have.has(id)) });
      }

      if (path.startsWith("/api/photo/")) {
        const id = decodeURIComponent(path.slice("/api/photo/".length));
        if (!id) return json({ error: "no id" }, 400);

        if (req.method === "PUT") {
          const bytes = await req.arrayBuffer();
          if (!bytes.byteLength) return json({ error: "empty body", id }, 400);
          if (bytes.byteLength > 50 * 1024 * 1024)
            return json({ error: "photo too large", id, size: bytes.byteLength }, 413);
          try {
            await env.BUCKET.put("photo/" + id, bytes, {
              httpMetadata: { contentType: req.headers.get("Content-Type") || "image/webp" },
            });
          } catch (e) {
            return json({ error: "store failed: " + String(e && e.message || e), id }, 502);
          }
          return json({ ok: true, size: bytes.byteLength });
        }
        if (req.method === "GET") {
          const obj = await env.BUCKET.get("photo/" + id);
          if (!obj) return json({ error: "not found" }, 404);
          return new Response(obj.body, {
            headers: {
              ...CORS,
              "Content-Type": obj.httpMetadata?.contentType || "image/webp",
              "Cache-Control": "public, max-age=31536000, immutable",
            },
          });
        }
      }

      /* Remove photos no record points at any more.
         Only safe once every device has synced its record changes. */
      if (path === "/api/gc" && req.method === "POST") {
        const { records } = await readIndex(env);
        const used = new Set();
        for (const r of Object.values(records)) {
          for (const id of [...(r.left || []), ...(r.right || [])]) used.add(id);
        }
        let removed = 0, freed = 0, cursor;
        let batch = [];
        do {
          const list = await env.BUCKET.list({ prefix: "photo/", cursor, limit: 1000 });
          for (const o of list.objects) {
            if (!used.has(o.key.slice(6))) { batch.push(o.key); freed += o.size; removed++; }
          }
          if (batch.length >= 500) { await env.BUCKET.delete(batch); batch = []; }
          cursor = list.truncated ? list.cursor : null;
        } while (cursor);
        if (batch.length) await env.BUCKET.delete(batch);
        return json({ removed, freed, kept: used.size });
      }

      if (path === "/api/stat" && req.method === "GET") {
        const { records } = await readIndex(env);
        let photos = 0, bytes = 0, cursor;
        do {
          const list = await env.BUCKET.list({ prefix: "photo/", cursor, limit: 1000 });
          for (const o of list.objects) { photos++; bytes += o.size; }
          cursor = list.truncated ? list.cursor : null;
        } while (cursor);
        const live = Object.values(records).filter(r => !r.del).length;
        return json({ hyenas: live, tombstones: Object.keys(records).length - live, photos, bytes });
      }

      return json({ error: "no such endpoint" }, 404);
    } catch (e) {
      const detail = String((e && e.stack) || (e && e.message) || e).slice(0, 500);
      console.error("worker error", req.method, path, detail);
      return json({ error: detail, where: req.method + " " + path }, 500);
    }
  },
};
