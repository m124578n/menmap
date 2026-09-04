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
  categories: Set<string>;  // 拉麵種類(多選,任一命中)
  beginner: boolean;        // 只看入門友善
}

interface Props {
  filters: Filters;
  cities: { name: string; count: number }[];
  districts: { name: string; count: number }[];
  categories: { name: string; count: number }[]; // 有分類資料才顯示「種類」
  hasNew: boolean; // 有新店才顯示「新店」chip
  onChange: (f: Filters) => void;
}

export default function FilterChips({ filters, cities, districts, categories, hasNew, onChange }: Props) {
  const [openMenu, setOpenMenu] = useState(false);
  const [openCat, setOpenCat] = useState(false);
  const catRef = useRef<HTMLDivElement>(null);
  const catBtnRef = useRef<HTMLButtonElement>(null);
  const catDropRef = useRef<HTMLDivElement>(null);
  const [catPos, setCatPos] = useState<{ top: number; left: number }>({ top: 0, left: 0 });
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

  // 種類下拉:定位與點外面/Esc 關閉(比照區域)
  useLayoutEffect(() => {
    if (openCat && catBtnRef.current) {
      const r = catBtnRef.current.getBoundingClientRect();
      setCatPos({ top: r.bottom + 6, left: r.left });
    }
  }, [openCat]);
  useEffect(() => {
    if (!openCat) return;
    const onDoc = (e: MouseEvent) => {
      const t = e.target as Node;
      if (catRef.current && !catRef.current.contains(t) &&
          catDropRef.current && !catDropRef.current.contains(t))
        setOpenCat(false);
    };
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        setOpenCat(false);
        catBtnRef.current?.focus();
      }
    };
    document.addEventListener("mousedown", onDoc);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onDoc);
      document.removeEventListener("keydown", onKey);
    };
  }, [openCat]);
  const toggleCategory = (c: string) => {
    const next = new Set(filters.categories);
    next.has(c) ? next.delete(c) : next.add(c);
    onChange({ ...filters, categories: next });
  };

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

      {categories.length > 0 && (
        <div className="chip-menu" ref={catRef}>
          <button
            ref={catBtnRef}
            className="chip"
            data-active={filters.categories.size > 0}
            aria-haspopup="menu"
            aria-expanded={openCat}
            onClick={() => setOpenCat((v) => !v)}
          >
            {filters.categories.size === 0 ? "種類" : `種類 · ${filters.categories.size}`}
            <ChevronDown size={14} />
          </button>
          {openCat &&
            createPortal(
              <div
                className="chip-dropdown panel"
                role="menu"
                aria-label="選擇拉麵種類"
                ref={catDropRef}
                style={{ position: "fixed", top: catPos.top, left: catPos.left }}
              >
                <div className="dist-group">主打湯頭 / 類型(可複選)</div>
                {categories.map((c) => (
                  <button
                    key={c.name}
                    className="dist-opt"
                    role="menuitemcheckbox"
                    aria-checked={filters.categories.has(c.name)}
                    data-active={filters.categories.has(c.name)}
                    onClick={() => toggleCategory(c.name)}
                  >
                    {filters.categories.has(c.name) ? <Check size={13} /> : <span style={{ width: 13 }} />}
                    {c.name}
                    <span className="count" style={{ marginLeft: "auto", opacity: 0.6 }}>{c.count}</span>
                  </button>
                ))}
              </div>,
              document.body
            )}
        </div>
      )}

      {categories.length > 0 && (
        <button
          className="chip"
          data-active={filters.beginner}
          aria-pressed={filters.beginner}
          title="口味大眾、點餐直覺、不用特別排隊的店"
          onClick={() => onChange({ ...filters, beginner: !filters.beginner })}
        >
          新手友善
        </button>
      )}

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
        filters.newOnly || filters.minRating > 0 || filters.price ||
        filters.categories.size > 0 || filters.beginner) && (
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
              categories: new Set(),
              beginner: false,
            })
          }
        >
          清除
        </button>
      )}
    </div>
  );
}
