import { useEffect, useLayoutEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { ChevronDown, Check } from "lucide-react";
import { PRICE_BANDS, type PriceBand } from "../lib/format";

export interface Filters {
  cities: Set<string>;      // 縣市層級(粗)
  districts: Set<string>;   // 行政區層級(細)
  openNow: boolean;
  lateNight: boolean;       // 深夜營業(打烊 ≥23:30 或跨午夜)
  newOnly: boolean;         // 只看新店
  minRating: number; // 0 = 不限
  price: PriceBand | null;  // 價格帶(單選;null = 不限)
}

interface Props {
  filters: Filters;
  cities: { name: string; count: number }[];
  districts: { name: string; count: number }[];
  hasNew: boolean; // 有新店才顯示「新店」chip
  onChange: (f: Filters) => void;
}

export default function FilterChips({ filters, cities, districts, hasNew, onChange }: Props) {
  const [openMenu, setOpenMenu] = useState(false);
  const menuRef = useRef<HTMLDivElement>(null);
  const btnRef = useRef<HTMLButtonElement>(null);
  const dropRef = useRef<HTMLDivElement>(null);
  const [pos, setPos] = useState<{ top: number; left: number }>({ top: 0, left: 0 });

  // 選單用 fixed 定位,避免被篩選列的 overflow 裁切
  useLayoutEffect(() => {
    if (openMenu && btnRef.current) {
      const r = btnRef.current.getBoundingClientRect();
      setPos({ top: r.bottom + 6, left: r.left });
    }
  }, [openMenu]);

  useEffect(() => {
    if (!openMenu) return;
    const onDoc = (e: MouseEvent) => {
      const t = e.target as Node;
      if (
        menuRef.current && !menuRef.current.contains(t) &&
        dropRef.current && !dropRef.current.contains(t)
      )
        setOpenMenu(false);
    };
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        setOpenMenu(false);
        btnRef.current?.focus();
      }
    };
    document.addEventListener("mousedown", onDoc);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onDoc);
      document.removeEventListener("keydown", onKey);
    };
  }, [openMenu]);

  const toggleDistrict = (d: string) => {
    const next = new Set(filters.districts);
    next.has(d) ? next.delete(d) : next.add(d);
    onChange({ ...filters, districts: next });
  };
  const toggleCity = (c: string) => {
    const next = new Set(filters.cities);
    next.has(c) ? next.delete(c) : next.add(c);
    onChange({ ...filters, cities: next });
  };

  const regionCount = filters.cities.size + filters.districts.size;
  const distLabel = regionCount === 0 ? "區域" : `區域 · ${regionCount}`;

  const ratings = [4.5, 4.0];

  return (
    <div className="filters">
      <div className="chip-menu" ref={menuRef}>
        <button
          ref={btnRef}
          className="chip"
          data-active={regionCount > 0}
          aria-haspopup="menu"
          aria-expanded={openMenu}
          onClick={() => setOpenMenu((v) => !v)}
        >
          {distLabel}
          <ChevronDown size={14} />
        </button>
        {openMenu &&
          createPortal(
            <div
              className="chip-dropdown panel"
              role="menu"
              aria-label="選擇區域"
              ref={dropRef}
              style={{ position: "fixed", top: pos.top, left: pos.left }}
            >
              {cities.length > 0 && (
                <div className="dist-group">縣市(整市)</div>
              )}
              {cities.map((c) => (
                <button
                  key={c.name}
                  className="dist-opt"
                  role="menuitemcheckbox"
                  aria-checked={filters.cities.has(c.name)}
                  data-active={filters.cities.has(c.name)}
                  onClick={() => toggleCity(c.name)}
                >
                  {filters.cities.has(c.name) ? (
                    <Check size={13} />
                  ) : (
                    <span style={{ width: 13 }} />
                  )}
                  {c.name}
                  <span className="count" style={{ marginLeft: "auto", opacity: 0.6 }}>
                    {c.count}
                  </span>
                </button>
              ))}
              {districts.length > 0 && <div className="dist-group">行政區</div>}
              {districts.map((d) => (
                <button
                  key={d.name}
                  className="dist-opt"
                  role="menuitemcheckbox"
                  aria-checked={filters.districts.has(d.name)}
                  data-active={filters.districts.has(d.name)}
                  onClick={() => toggleDistrict(d.name)}
                >
                  {filters.districts.has(d.name) ? (
                    <Check size={13} />
                  ) : (
                    <span style={{ width: 13 }} />
                  )}
                  {d.name}
                  <span className="count" style={{ marginLeft: "auto", opacity: 0.6 }}>
                    {d.count}
                  </span>
                </button>
              ))}
            </div>,
            document.body
          )}
      </div>

      <button
        className="chip"
        data-active={filters.openNow}
        aria-pressed={filters.openNow}
        onClick={() => onChange({ ...filters, openNow: !filters.openNow })}
      >
        營業中
      </button>

      <button
        className="chip"
        data-active={filters.lateNight}
        aria-pressed={filters.lateNight}
        onClick={() => onChange({ ...filters, lateNight: !filters.lateNight })}
      >
        深夜營業
      </button>

      {hasNew && (
        <button
          className="chip"
          data-active={filters.newOnly}
          aria-pressed={filters.newOnly}
          onClick={() => onChange({ ...filters, newOnly: !filters.newOnly })}
        >
          新店
        </button>
      )}

      {ratings.map((r) => (
        <button
          key={r}
          className="chip"
          data-active={filters.minRating === r}
          aria-pressed={filters.minRating === r}
          aria-label={`評分 ${r} 以上`}
          onClick={() =>
            onChange({ ...filters, minRating: filters.minRating === r ? 0 : r })
          }
        >
          ★ {r}+
        </button>
      ))}

      {PRICE_BANDS.map((b) => (
        <button
          key={b.key}
          className="chip"
          data-active={filters.price === b.key}
          aria-pressed={filters.price === b.key}
          aria-label={`價格 ${b.label}`}
          title={b.desc}
          onClick={() =>
            onChange({ ...filters, price: filters.price === b.key ? null : b.key })
          }
        >
          {b.label}
        </button>
      ))}

      {(regionCount > 0 || filters.openNow || filters.lateNight ||
        filters.newOnly || filters.minRating > 0 || filters.price) && (
        <button
          className="chip"
          onClick={() =>
            onChange({
              cities: new Set(),
              districts: new Set(),
              openNow: false,
              lateNight: false,
              newOnly: false,
              price: null,
              minRating: 0,
            })
          }
        >
          清除
        </button>
      )}
    </div>
  );
}
