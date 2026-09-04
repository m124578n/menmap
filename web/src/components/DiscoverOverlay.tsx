import { useState } from "react";
import { X, Trophy, TrendingUp, Sprout, Newspaper } from "lucide-react";
import type { DiscoverData, Shop } from "../types";
import { useDiscover } from "../hooks/useDiscover";
import { StatusDot } from "./StatusBadge";
import { formatCount, statusLabel } from "../lib/format";

interface Props {
  shops: Shop[];
  onSelect: (ftid: string) => void;
  onClose: () => void;
}

type Tab = "hot" | "rising" | "starter" | "weekly";
const TABS: { key: Tab; label: string; icon: React.ReactNode }[] = [
  { key: "hot", label: "熱門", icon: <Trophy size={14} /> },
  { key: "rising", label: "竄紅", icon: <TrendingUp size={14} /> },
  { key: "starter", label: "入門", icon: <Sprout size={14} /> },
  { key: "weekly", label: "本週動態", icon: <Newspaper size={14} /> },
];

/** 麵榜:熱門/竄紅/入門三個榜 + 本週動態週報。全部由 discover.json 供資料。 */
export default function DiscoverOverlay({ shops, onSelect, onClose }: Props) {
  const [tab, setTab] = useState<Tab>("hot");
  const disc = useDiscover(true);
  const byId = new Map(shops.map((s) => [s.ftid, s]));

  const pick = (ftid: string) => {
    onSelect(ftid);
    onClose();
  };

  return (
    <div className="dice-overlay" onClick={onClose}>
      <div
        className="discover-card panel noren-top"
        role="dialog"
        aria-modal="true"
        aria-label="麵榜"
        onClick={(e) => e.stopPropagation()}
      >
        <button className="close-btn" onClick={onClose} aria-label="關閉">
          <X size={18} />
        </button>
        <h2 className="about-title">
          <span className="stamp">榜</span> 麵榜
        </h2>
        <div className="discover-tabs" role="tablist">
          {TABS.map((t) => (
            <button
              key={t.key}
              role="tab"
              aria-selected={tab === t.key}
              className="chip"
              data-active={tab === t.key}
              onClick={() => setTab(t.key)}
            >
              {t.icon} {t.label}
            </button>
          ))}
        </div>

        <div className="discover-body">
          {disc.status === "loading" && <div className="empty">載入中…</div>}
          {disc.status === "error" && <div className="empty">榜單暫時載入不了,請稍後再試。</div>}
          {disc.status === "ok" && (
            <>
              {tab === "hot" && (
                <Ranked
                  intro="評分 × 評論數的貝氏平均:評論少的高分會被拉回全體平均,避免小樣本衝榜。"
                  items={disc.data.hot.map((h) => ({ ftid: h.ftid }))}
                  byId={byId}
                  onPick={pick}
                />
              )}
              {tab === "rising" && (
                <Ranked
                  intro={`近 ${disc.data.window.days} 天評論數增加最多的店(每日快照差分)。`}
                  items={disc.data.rising.map((r) => ({
                    ftid: r.ftid,
                    note: `+${r.delta} 則 / ${r.days} 天`,
                  }))}
                  byId={byId}
                  onPick={pick}
                  emptyText={
                    disc.data.window.days < 2
                      ? "資料累積中:每日快照跑滿幾天後,這裡會列出評論數竄升的店。"
                      : "這幾天沒有明顯竄紅的店。"
                  }
                />
              )}
              {tab === "starter" && (
                <Ranked
                  intro="給想開始吃拉麵的人:評論多、評分穩(4.3+)、價格親民、目前營業中。"
                  items={disc.data.starter.map((s) => ({ ftid: s.ftid }))}
                  byId={byId}
                  onPick={pick}
                />
              )}
              {tab === "weekly" && <Weekly data={disc.data} byId={byId} onPick={pick} />}
              <p className="discover-foot">
                資料更新:{disc.data.generated_at.replace("T", " ").slice(0, 16)}
              </p>
            </>
          )}
        </div>
      </div>
    </div>
  );
}

function Row({
  rank,
  shop,
  note,
  onPick,
}: {
  rank?: number;
  shop: Shop;
  note?: string;
  onPick: (ftid: string) => void;
}) {
  return (
    <button className="card discover-row" onClick={() => onPick(shop.ftid)}>
      {rank != null && <span className="discover-rank" data-top={rank <= 3}>{rank}</span>}
      <div className="card-body">
        <div className="card-name">
          <StatusDot status={shop.status} />
          <span>{shop.name}</span>
          {shop.is_new && <span className="new-badge">NEW</span>}
        </div>
        <div className="card-meta">
          {shop.district && <span>{shop.district}</span>}
          {shop.rating != null && (
            <span className="card-rating">
              <span className="star">★</span> {shop.rating.toFixed(1)}
              {shop.rating_count != null && ` (${formatCount(shop.rating_count)})`}
            </span>
          )}
          {shop.price && <span>{shop.price}</span>}
          {note && <span className="discover-note">{note}</span>}
        </div>
      </div>
    </button>
  );
}

function Ranked({
  intro,
  items,
  byId,
  onPick,
  emptyText = "目前沒有符合的店。",
}: {
  intro: string;
  items: { ftid: string; note?: string }[];
  byId: Map<string, Shop>;
  onPick: (ftid: string) => void;
  emptyText?: string;
}) {
  const rows = items.map((it) => ({ ...it, shop: byId.get(it.ftid) })).filter((it) => it.shop);
  return (
    <>
      <p className="discover-intro">{intro}</p>
      {rows.length === 0 ? (
        <div className="empty">{emptyText}</div>
      ) : (
        <div className="list">
          {rows.map((it, i) => (
            <Row key={it.ftid} rank={i + 1} shop={it.shop!} note={it.note} onPick={onPick} />
          ))}
        </div>
      )}
    </>
  );
}

function Weekly({
  data,
  byId,
  onPick,
}: {
  data: DiscoverData;
  byId: Map<string, Shop>;
  onPick: (ftid: string) => void;
}) {
  const w = data.weekly;
  const sec = (title: string, rows: { ftid: string; note?: string }[], empty: string) => {
    const list = rows.map((r) => ({ ...r, shop: byId.get(r.ftid) })).filter((r) => r.shop);
    return (
      <section className="discover-section">
        <h3>
          {title} <span className="count">{list.length}</span>
        </h3>
        {list.length === 0 ? (
          <p className="discover-empty">{empty}</p>
        ) : (
          <div className="list">
            {list.map((r) => (
              <Row key={r.ftid + (r.note ?? "")} shop={r.shop!} note={r.note} onPick={onPick} />
            ))}
          </div>
        )}
      </section>
    );
  };
  const total =
    w.new_shops.length + w.status_changes.length + w.rating_jumps.length +
    w.hours_changes.length + w.renames.length;
  return (
    <>
      <p className="discover-intro">
        {data.window.from} ~ {data.window.to} 的雙北拉麵動態,來自每日快照的差分
        {data.window.days < 2 && ";每日快照跑滿幾天後內容會多起來"}。
      </p>
      {total === 0 && data.window.days < 2 && (
        <div className="empty">資料累積中,過幾天再來看看。</div>
      )}
      {sec("新收錄", w.new_shops.map((n) => ({ ftid: n.ftid, note: n.added_at })), "本週沒有新收錄的店。")}
      {sec(
        "營業狀態變動",
        w.status_changes.map((s) => ({
          ftid: s.ftid,
          note: `${statusLabel(s.from)} → ${statusLabel(s.to)}`,
        })),
        "本週沒有店家歇業或恢復營業。"
      )}
      {sec(
        "評分變動",
        w.rating_jumps.map((r) => ({
          ftid: r.ftid,
          note: `${r.from.toFixed(1)} → ${r.to.toFixed(1)}`,
        })),
        "本週沒有明顯的評分變動。"
      )}
      {sec("營業時間調整", w.hours_changes, "本週沒有店家調整營業時間。")}
      {sec(
        "改名 / 搬家",
        w.renames.map((r) => ({
          ftid: r.ftid,
          note: `${r.field === "name" ? "改名" : "地址"}:${r.old} → ${r.new}`,
        })),
        "本週沒有店家改名或搬家。"
      )}
    </>
  );
}
