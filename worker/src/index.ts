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

  // 兩個採集後端可能各存一份同樣的貼文,以文字去重
  const postsRes = await db
    .prepare(
      `SELECT text, MAX(ts) ts, MAX(link) link, MAX(photo) photo
       FROM post WHERE ftid = ? GROUP BY text ORDER BY ts DESC`
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

  // 資料每天更新一次:讓 CDN/瀏覽器快取幾分鐘,減少 D1 讀取
  c.header("Cache-Control", "public, max-age=300, s-maxage=600");
  return c.json({
    ftid,
    found: true,
    name: shop?.name ?? null,
    address: shop?.address ?? null,
    phone: (latest?.phone ?? shop?.phone) ?? null,
    website: (latest?.website ?? shop?.website) ?? null,
    place_id: shop?.place_id ?? null,
    cover_photo: shop?.cover_photo ?? null,
    fan_page: shop?.fan_page ?? null,
    menu_photos: safeParse(shop?.menu_photos_json as string, [] as string[]),
    closed_at: shop?.closed_at ?? null,
    categories: safeParse(shop?.categories_json as string, [] as string[]),
    beginner_friendly: shop?.beginner_friendly == null ? null : !!shop.beginner_friendly,
    posts: (postsRes.results ?? []).map((p: any) => ({
      text: p.text,
      ts: p.ts,
      link: p.link,
      photo: p.photo,
    })),
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
