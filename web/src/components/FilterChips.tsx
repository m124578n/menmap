import { useEffect, useLayoutEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { ChevronDown, Check } from "lucide-react";

export interface Filters {
  districts: Set<string>;
  openNow: boolean;
  minRating: number; // 0 = 不限
}

interface Props {
  filters: Filters;
  districts: { name: string; count: number }[];
  onChange: (f: Filters) => void;
}

export default function FilterChips({ filters, districts, onChange }: Props) {
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
    document.addEventListener("mousedown", onDoc);
    return () => document.removeEventListener("mousedown", onDoc);
  }, [openMenu]);

  const toggleDistrict = (d: string) => {
    const next = new Set(filters.districts);
    next.has(d) ? next.delete(d) : next.add(d);
    onChange({ ...filters, districts: next });
  };

  const distLabel =
    filters.districts.size === 0
      ? "區域"
      : `區域 · ${filters.districts.size}`;

  const ratings = [4.5, 4.0];

  return (
    <div className="filters">
      <div className="chip-menu" ref={menuRef}>
        <button
          ref={btnRef}
          className="chip"
          data-active={filters.districts.size > 0}
          onClick={() => setOpenMenu((v) => !v)}
        >
          {distLabel}
          <ChevronDown size={14} />
        </button>
        {openMenu &&
          createPortal(
            <div
              className="chip-dropdown panel"
              ref={dropRef}
              style={{ position: "fixed", top: pos.top, left: pos.left }}
            >
              {districts.map((d) => (
                <button
                  key={d.name}
                  className="dist-opt"
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
        onClick={() => onChange({ ...filters, openNow: !filters.openNow })}
      >
        營業中
      </button>

      {ratings.map((r) => (
        <button
          key={r}
          className="chip"
          data-active={filters.minRating === r}
          onClick={() =>
            onChange({ ...filters, minRating: filters.minRating === r ? 0 : r })
          }
        >
          ★ {r}+
        </button>
      ))}

      {(filters.districts.size > 0 || filters.openNow || filters.minRating > 0) && (
        <button
          className="chip"
          onClick={() =>
            onChange({ districts: new Set(), openNow: false, minRating: 0 })
          }
        >
          清除
        </button>
      )}
    </div>
  );
}
