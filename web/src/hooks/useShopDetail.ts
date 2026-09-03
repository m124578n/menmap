import { useEffect, useState } from "react";

export interface Review {
  author: string | null;
  stars: number | null;
  date_rel: string | null;
  text: string | null;
  photos: string[];
}

export interface MerchantPost {
  text: string | null;
  ts: number | null;
  link: string | null;
  photo: string | null;
}

export interface ShopDetailData {
  ftid: string;
  found: boolean;
  name: string | null;
  address: string | null;
  phone: string | null;
  website: string | null;
  place_id: string | null;
  cover_photo: string | null;
  fan_page: string | null;
  menu_photos: string[];
  closed_at: string | null;
  posts: MerchantPost[];
  latest: {
    captured_at: string;
    business_status: string | null;
    opening_hours: [string, string[]][] | null;
    price_text: string | null;
    rating: number | null;
    rating_count: number | null;
    is_rich: boolean;
  } | null;
  history: {
    captured_at: string;
    business_status: string | null;
    rating: number | null;
    rating_count: number | null;
  }[];
  reviews: Review[];
}

type State =
  | { status: "loading" }
  | { status: "empty" } // API 回應但這家店還沒有詳情快照
  | { status: "error"; error: string }
  | { status: "ok"; data: ShopDetailData };

/**
 * API 位置。本機開發走 Vite proxy(空字串 = 同源 /api);
 * 部署到 Pages 時 Worker 在另一個網域,build 時設 VITE_API_BASE=https://menmap-api.<帳號>.workers.dev
 * (Worker 已開 CORS GET)。若之後把 Worker 綁到同網域的 /api/* 路由,就不用設。
 */
const API_BASE = (import.meta.env.VITE_API_BASE ?? "").replace(/\/$/, "");

export function useShopDetail(ftid: string | null): State {
  const [state, setState] = useState<State>({ status: "loading" });

  useEffect(() => {
    if (!ftid) return;
    let alive = true;
    setState({ status: "loading" });
    fetch(`${API_BASE}/api/shop/${encodeURIComponent(ftid)}`)
      .then(async (r) => {
        if (r.status === 404) return { found: false } as ShopDetailData;
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        return (await r.json()) as ShopDetailData;
      })
      .then((data) => {
        if (!alive) return;
        if (!data.found) setState({ status: "empty" });
        else setState({ status: "ok", data });
      })
      .catch((e) => {
        if (alive) setState({ status: "error", error: String(e) });
      });
    return () => {
      alive = false;
    };
  }, [ftid]);

  return state;
}
