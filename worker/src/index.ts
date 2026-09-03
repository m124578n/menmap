import { Hono } from "hono";
import { cors } from "hono/cors";

interface Env {
  DB: D1Database;
}

const app = new Hono<{ Bindings: Env }>();

// dev 期 Vite 走 proxy 不會有 CORS;直接呼叫時仍放行 GET
app.use("/api/*", cors({ origin: "*", allowMethods: ["GET"] }));

app.get("/api/health", (c) => c.json({ ok: true }));

/** 單店詳情:shop + 最新快照 + 近期歷史 + 最新評論 */
app.get("/api/shop/:ftid", async (c) => {
  const ftid = c.req.param("ftid");
  const db = c.env.DB;

  const shop = await db
    .prepare("SELECT * FROM shop WHERE ftid = ?")
    .bind(ftid)
    .first();

  const latest = await db
    .prepare(
      `SELECT * FROM snapshot WHERE ftid = ? AND ok = 1
       ORDER BY captured_at DESC LIMIT 1`
    )
    .bind(ftid)
    .first();

  if (!shop && !latest) {
    return c.json({ ftid, found: false }, 404);
  }

  const historyRes = await db
    .prepare(
      `SELECT captured_at, business_status, rating, user_rating_count
       FROM snapshot WHERE ftid = ? AND ok = 1
       ORDER BY captured_at DESC LIMIT 30`
    )
    .bind(ftid)
    .all();

  const reviewsRes = await db
    .prepare(
      `SELECT author, stars, date_rel, text, photos_json
       FROM review WHERE ftid = ? ORDER BY seq ASC`
    )
    .bind(ftid)
    .all();

  const reviews = (reviewsRes.results ?? []).map((r: any) => ({
    author: r.author,
    stars: r.stars,
    date_rel: r.date_rel,
    text: r.text,
    photos: safeParse(r.photos_json, []),
  }));

  const history = (historyRes.results ?? []).map((h: any) => ({
    captured_at: h.captured_at,
    business_status: h.business_status,
    rating: h.rating,
    rating_count: h.user_rating_count,
  }));

  return c.json({
    ftid,
    found: true,
    name: shop?.name ?? null,
    address: shop?.address ?? null,
    phone: (latest?.phone ?? shop?.phone) ?? null,
    website: (latest?.website ?? shop?.website) ?? null,
    place_id: shop?.place_id ?? null,
    cover_photo: shop?.cover_photo ?? null,
    latest: latest
      ? {
          captured_at: latest.captured_at,
          business_status: latest.business_status,
          opening_hours: safeParse(latest.opening_hours_json as string, null),
          price_text: latest.price_text,
          rating: latest.rating,
          rating_count: latest.user_rating_count,
          is_rich: !!latest.is_rich,
        }
      : null,
    history,
    reviews,
  });
});

function safeParse<T>(s: string | null | undefined, fallback: T): T {
  if (!s) return fallback;
  try {
    return JSON.parse(s) as T;
  } catch {
    return fallback;
  }
}

export default app;
