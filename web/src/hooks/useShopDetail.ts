import { useEffect, useState } from "react";

export interface Review {
  author: string | null;
  stars: number | null;
  date_rel: string | null;
  text: string | null;
  photos: string[];
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

export function useShopDetail(ftid: string | null): State {
  const [state, setState] = useState<State>({ status: "loading" });

  useEffect(() => {
    if (!ftid) return;
    let alive = true;
    setState({ status: "loading" });
    fetch(`/api/shop/${encodeURIComponent(ftid)}`)
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
