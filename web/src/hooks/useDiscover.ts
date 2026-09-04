import { useEffect, useState } from "react";
import type { DiscoverData } from "../types";

type State =
  | { status: "idle" | "loading" }
  | { status: "error"; error: string }
  | { status: "ok"; data: DiscoverData };

/** 麵榜/本週動態:開啟時才抓 discover.json(每天更新,和 shops.json 同一批產出)。 */
export function useDiscover(enabled: boolean): State {
  const [state, setState] = useState<State>({ status: "idle" });

  useEffect(() => {
    if (!enabled || state.status === "ok") return;
    let alive = true;
    setState({ status: "loading" });
    fetch(`${import.meta.env.BASE_URL}discover.json`)
      .then((r) => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        return r.json() as Promise<DiscoverData>;
      })
      .then((data) => alive && setState({ status: "ok", data }))
      .catch((e) => alive && setState({ status: "error", error: String(e) }));
    return () => {
      alive = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [enabled]);

  return state;
}
