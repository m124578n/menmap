import { useEffect, useMemo, useState } from "react";
import type { LngLatBounds } from "maplibre-gl";
import { Search, X, Moon, Sun, PanelLeftClose, PanelLeftOpen, Dices } from "lucide-react";
import { useShops } from "./hooks/useShops";
import { useTheme } from "./hooks/useTheme";
import { useDice } from "./hooks/useDice";
import MapView from "./components/MapView";
import FilterChips, { type Filters } from "./components/FilterChips";
import ShopList from "./components/ShopList";
import DetailPanel from "./components/DetailPanel";
import DiceOverlay from "./components/DiceOverlay";
import { isLateNight, isOpenNow } from "./lib/hours";
import type { Shop } from "./types";

export default function App() {
  const { shops, loading, error } = useShops();
  const { theme, toggle } = useTheme();

  const [search, setSearch] = useState("");
  const [filters, setFilters] = useState<Filters>({
    cities: new Set(),
    districts: new Set(),
    openNow: false,
    lateNight: false,
    newOnly: false,
    minRating: 0,
  });
  const [selected, setSelected] = useState<string | null>(
    () => decodeURIComponent(window.location.hash.slice(1)) || null
  );
  const [bounds, setBounds] = useState<LngLatBounds | null>(null);
  const [collapsed, setCollapsed] = useState(false);

  // 區域清單(依數量排序)
  const districts = useMemo(() => {
    const m = new Map<string, number>();
    for (const s of shops) if (s.district) m.set(s.district, (m.get(s.district) ?? 0) + 1);
    return [...m.entries()]
      .map(([name, count]) => ({ name, count }))
      .sort((a, b) => b.count - a.count);
  }, [shops]);

  // 縣市清單
  const cities = useMemo(() => {
    const m = new Map<string, number>();
    for (const s of shops) if (s.city) m.set(s.city, (m.get(s.city) ?? 0) + 1);
    return [...m.entries()]
      .map(([name, count]) => ({ name, count }))
      .sort((a, b) => b.count - a.count);
  }, [shops]);

  // 依 search + filters 篩選(給地圖標記用,不含地圖範圍)
  const matched = useMemo(() => {
    const q = search.trim().toLowerCase();
    const hasRegion = filters.cities.size > 0 || filters.districts.size > 0;
    return shops.filter((s) => {
      if (q && !(s.name ?? "").toLowerCase().includes(q)) return false;
      // 區域:選了縣市或區才過濾;縣市(粗)或區(細)任一命中即可
      if (hasRegion) {
        const cityHit = !!(s.city && filters.cities.has(s.city));
        const distHit = !!(s.district && filters.districts.has(s.district));
        if (!cityHit && !distHit) return false;
      }
      if (filters.openNow) {
        // 有營業時間就精準判斷「現在營業中」;沒有就退回營業狀態
        const open = isOpenNow(s.hours);
        if (open === false) return false;
        if (open === null && s.status !== "OPERATIONAL") return false;
      }
      if (filters.lateNight && !isLateNight(s.hours)) return false;
      if (filters.newOnly && !s.is_new) return false;
      if (filters.minRating > 0 && (s.rating ?? 0) < filters.minRating) return false;
      return true;
    });
  }, [shops, search, filters]);

  const hasNew = useMemo(() => shops.some((s) => s.is_new), [shops]);

  const dice = useDice(matched);

  // 列表:再套目前地圖可視範圍
  const listShops = useMemo(() => {
    if (!bounds) return matched;
    return matched.filter((s) => bounds.contains([s.lng, s.lat]));
  }, [matched, bounds]);

  const selectedShop: Shop | undefined = useMemo(
    () => shops.find((s) => s.ftid === selected),
    [shops, selected]
  );

  // 分享連結:#ftid ↔ 選中的店(初始值已從 hash 讀入)
  useEffect(() => {
    const url = selected
      ? `#${encodeURIComponent(selected)}`
      : window.location.pathname + window.location.search;
    window.history.replaceState(null, "", url);
  }, [selected]);

  // 分頁標題跟著選中的店走(分享/多分頁時好辨認)
  useEffect(() => {
    document.title = selectedShop?.name
      ? `${selectedShop.name} · 雙北拉麵地圖`
      : "雙北拉麵地圖 · menmap";
  }, [selectedShop]);

  // Esc:關閉骰子 → 關閉詳情
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key !== "Escape") return;
      if (dice.phase !== "idle") dice.reset();
      else if (selected) setSelected(null);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [dice, selected]);

  return (
    <div className="app">
      <MapView
        shops={matched}
        selected={selected}
        theme={theme}
        onSelect={setSelected}
        onBoundsChange={setBounds}
      />

      <div className="topbar">
        <div className="brand panel">
          <span className="stamp">麺</span>
          <span>
            雙北拉麵地圖 <span className="brand-name-sub">menmap</span>
          </span>
        </div>
        <div className="searchbar panel">
          <Search size={18} color="var(--fg-muted)" />
          <input
            type="search"
            enterKeyHint="search"
            autoComplete="off"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="搜尋店名…"
            aria-label="搜尋店名"
          />
          {search && (
            <button className="icon-btn" style={{ width: 28, height: 28 }} onClick={() => setSearch("")} aria-label="清除">
              <X size={16} />
            </button>
          )}
        </div>
        <button
          className="icon-btn panel dice-trigger"
          onClick={dice.roll}
          disabled={dice.count === 0}
          aria-label="拉麵骰子:隨機選一間"
          title={`拉麵骰子(從 ${dice.count} 家中選)`}
        >
          <Dices size={18} />
        </button>
        <button className="icon-btn panel" onClick={toggle} aria-label="切換深淺色">
          {theme === "dark" ? <Sun size={18} /> : <Moon size={18} />}
        </button>
        <button
          className="icon-btn panel desktop-only"
          onClick={() => setCollapsed((v) => !v)}
          aria-label={collapsed ? "展開列表" : "收合列表"}
        >
          {collapsed ? <PanelLeftOpen size={18} /> : <PanelLeftClose size={18} />}
        </button>
      </div>

      <FilterChips
        filters={filters}
        cities={cities}
        districts={districts}
        hasNew={hasNew}
        onChange={setFilters}
      />

      {!selectedShop && (
        <section className="drawer panel" data-collapsed={collapsed}>
          <button
            type="button"
            className="drawer-handle"
            onClick={() => setCollapsed((v) => !v)}
            aria-label={collapsed ? "展開列表" : "收合列表"}
            aria-expanded={!collapsed}
          />
          <div className="drawer-head">
            <span className="count-label">
              {loading ? "載入中…" : error ? "載入失敗" : <><strong>{listShops.length}</strong> 家(可視範圍內)</>}
            </span>
          </div>
          {!loading && !error && (
            <ShopList shops={listShops} selected={selected} onSelect={setSelected} />
          )}
          {error && (
            <div className="empty">
              店家資料暫時載入不了,請稍後重新整理。
              {import.meta.env.DEV && <><br /><code>{error}</code></>}
            </div>
          )}
        </section>
      )}

      {selectedShop && (
        <DetailPanel shop={selectedShop} onClose={() => setSelected(null)} />
      )}

      {dice.phase !== "idle" && (
        <DiceOverlay
          phase={dice.phase}
          shop={dice.display}
          onChoose={(ftid) => {
            setSelected(ftid);
            dice.reset();
          }}
          onReroll={dice.roll}
          onClose={dice.reset}
        />
      )}
    </div>
  );
}
