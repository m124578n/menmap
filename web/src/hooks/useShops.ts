import { useEffect, useState } from "react";
import type { Shop, ShopsData } from "../types";

interface State {
  shops: Shop[];
  loading: boolean;
  error: string | null;
}

export function useShops(): State {
  const [state, setState] = useState<State>({
    shops: [],
    loading: true,
    error: null,
  });

  useEffect(() => {
    let alive = true;
    fetch(`${import.meta.env.BASE_URL}shops.json`)
      .then((r) => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        return r.json() as Promise<ShopsData>;
      })
      .then((data) => {
        if (!alive) return;
        const shops = data.shops
          .filter((s) => typeof s.lat === "number" && typeof s.lng === "number")
          .map((s) => ({ ...s, categories: s.categories ?? [], beginner: s.beginner ?? null }));
        setState({ shops, loading: false, error: null });
      })
      .catch((e) => {
        if (alive) setState({ shops: [], loading: false, error: String(e) });
      });
    return () => {
      alive = false;
    };
  }, []);

  return state;
}
