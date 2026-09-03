import { useMemo, useState } from "react";
import type { LngLatBounds } from "maplibre-gl";
import { Search, X, Moon, Sun, PanelLeftClose, PanelLeftOpen } from "lucide-react";
import { useShops } from "./hooks/useShops";
import { useTheme } from "./hooks/useTheme";
import MapView from "./components/MapView";
import FilterChips, { type Filters } from "./components/FilterChips";
import ShopList from "./components/ShopList";
import DetailPanel from "./components/DetailPanel";
import type { Shop } from "./types";

export default function App() {
  const { shops, loading, error } = useShops();
  const { theme, toggle } = useTheme();

  const [search, setSearch] = useState("");
  const [filters, setFilters] = useState<Filters>({
    districts: new Set(),
    openNow: false,
    minRating: 0,
  });
  const [selected, setSelected] = useState<string | null>(null);
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

  // 依 search + filters 篩選(給地圖標記用,不含地圖範圍)
  const matched = useMemo(() => {
    const q = search.trim().toLowerCase();
    return shops.filter((s) => {
      if (q && !(s.name ?? "").toLowerCase().includes(q)) return false;
      if (filters.districts.size > 0 && !(s.district && filters.districts.has(s.district)))
        return false;
      if (filters.openNow && s.status !== "OPERATIONAL") return false;
      if (filters.minRating > 0 && (s.rating ?? 0) < filters.minRating) return false;
      return true;
    });
  }, [shops, search, filters]);

  // 列表:再套目前地圖可視範圍
  const listShops = useMemo(() => {
    if (!bounds) return matched;
    return matched.filter((s) => bounds.contains([s.lng, s.lat]));
  }, [matched, bounds]);

  const selectedShop: Shop | undefined = useMemo(
    () => shops.find((s) => s.ftid === selected),
    [shops, selected]
  );

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

      <FilterChips filters={filters} districts={districts} onChange={setFilters} />

      {!selectedShop && (
        <section className="drawer panel" data-collapsed={collapsed}>
          <div className="drawer-handle" onClick={() => setCollapsed((v) => !v)} />
          <div className="drawer-head">
            <span className="count-label">
              {loading ? "載入中…" : error ? "載入失敗" : <><strong>{listShops.length}</strong> 家(可視範圍內)</>}
            </span>
          </div>
          {!loading && !error && (
            <ShopList shops={listShops} selected={selected} onSelect={setSelected} />
          )}
          {error && <div className="empty">shops.json 載入失敗:{error}</div>}
        </section>
      )}

      {selectedShop && (
        <DetailPanel shop={selectedShop} onClose={() => setSelected(null)} />
      )}
    </div>
  );
}
