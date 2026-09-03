import { X, ExternalLink, Star, MapPin, Tag, Phone, Globe, Clock } from "lucide-react";
import type { Shop, BusinessStatus } from "../types";
import { StatusBadge } from "./StatusBadge";
import { formatCount, statusColor, hiRes } from "../lib/format";
import { useShopDetail, type Review } from "../hooks/useShopDetail";

interface Props {
  shop: Shop;
  onClose: () => void;
}

const WEEKDAYS = ["星期日", "星期一", "星期二", "星期三", "星期四", "星期五", "星期六"];

export default function DetailPanel({ shop, onClose }: Props) {
  const detail = useShopDetail(shop.ftid);
  const d = detail.status === "ok" ? detail.data : null;

  const status: BusinessStatus = (d?.latest?.business_status as BusinessStatus) ?? shop.status;
  const rating = d?.latest?.rating ?? shop.rating;
  const ratingCount = d?.latest?.rating_count ?? shop.rating_count;
  const price = d?.latest?.price_text ?? shop.price;
  const cover = d?.cover_photo ?? shop.cover;

  return (
    <aside className="detail panel noren-top" role="dialog" aria-label={shop.name ?? "店家詳情"}>
      <button className="close-btn" onClick={onClose} aria-label="關閉">
        <X size={18} />
      </button>
      <div className="detail-scroll">
        {cover && (
          <img
            className="detail-cover"
            src={hiRes(cover, "w1000")}
            alt=""
            loading="lazy"
            onError={(e) => {
              e.currentTarget.style.display = "none";
            }}
          />
        )}

        <div className="detail-head">
          <h2 className="detail-name">{shop.name}</h2>
          <div className="detail-sub">
            {[shop.city, shop.district].filter(Boolean).join(" · ")}
          </div>
          <div style={{ marginTop: 10 }}>
            <StatusBadge status={status} />
          </div>
        </div>

        {/* 基本資料 */}
        <div className="detail-section">
          <h3>基本資料</h3>
          {rating != null && (
            <div className="kv">
              <span className="k">
                <Star size={14} style={{ verticalAlign: "-2px" }} /> 評分
              </span>
              <span>
                {rating.toFixed(1)}
                {ratingCount != null && ` · ${formatCount(ratingCount)} 則評論`}
              </span>
            </div>
          )}
          {price && (
            <div className="kv">
              <span className="k">價位</span>
              <span>{price}</span>
            </div>
          )}
          {shop.types.length > 0 && (
            <div className="kv">
              <span className="k">
                <Tag size={14} style={{ verticalAlign: "-2px" }} /> 類別
              </span>
              <span>{shop.types.join("、")}</span>
            </div>
          )}
          {d?.phone && (
            <div className="kv">
              <span className="k">
                <Phone size={14} style={{ verticalAlign: "-2px" }} /> 電話
              </span>
              <a href={`tel:${d.phone.replace(/\s/g, "")}`}>{d.phone}</a>
            </div>
          )}
          {d?.website && (
            <div className="kv">
              <span className="k">
                <Globe size={14} style={{ verticalAlign: "-2px" }} /> 網站
              </span>
              <a href={d.website} target="_blank" rel="noreferrer" className="truncate-link">
                官方網站
              </a>
            </div>
          )}
        </div>

        {/* 詳情 API 狀態 */}
        {detail.status === "loading" && (
          <div className="detail-section detail-note">載入詳情中…</div>
        )}
        {detail.status === "empty" && (
          <div className="detail-section detail-note">
            這家店還沒有詳情快照(每日採集會逐步覆蓋)。已顯示地圖與基本資料。
          </div>
        )}
        {detail.status === "error" && (
          <div className="detail-section detail-note">
            詳情 API 無法連線({detail.error})。請確認 worker(wrangler dev)有啟動。
          </div>
        )}

        {/* 營業時間 */}
        {d?.latest?.opening_hours && d.latest.opening_hours.length > 0 && (
          <div className="detail-section">
            <h3>
              <Clock size={12} style={{ verticalAlign: "-1px" }} /> 營業時間
            </h3>
            <Hours hours={d.latest.opening_hours} />
          </div>
        )}

        {/* 評分趨勢 */}
        {d && d.history.length >= 2 && (
          <div className="detail-section">
            <h3>近期評分趨勢</h3>
            <Trend
              points={d.history
                .slice()
                .reverse()
                .map((h) => h.rating)}
            />
          </div>
        )}

        {/* 評論 */}
        {d && d.reviews.length > 0 && (
          <div className="detail-section">
            <h3>最新評論({d.reviews.length})</h3>
            {d.reviews.map((r, i) => (
              <ReviewItem key={i} r={r} />
            ))}
          </div>
        )}

        {shop.maps_url && (
          <a className="maps-link" href={shop.maps_url} target="_blank" rel="noreferrer">
            <MapPin size={16} /> 在 Google 地圖開啟
            <ExternalLink size={14} style={{ marginLeft: "auto" }} />
          </a>
        )}
      </div>
    </aside>
  );
}

function Hours({ hours }: { hours: [string, string[]][] }) {
  const todayName = WEEKDAYS[new Date().getDay()];
  return (
    <div>
      {hours.map(([day, spans], i) => (
        <div className="hours-row" data-today={day === todayName} key={i}>
          <span className="day">{day}</span>
          <span>{spans.length ? spans.join("、") : "休息"}</span>
        </div>
      ))}
    </div>
  );
}

function ReviewItem({ r }: { r: Review }) {
  return (
    <div className="review">
      <div className="review-head">
        <span className="review-author">{r.author ?? "匿名"}</span>
        {r.stars != null && <span className="review-stars">{"★".repeat(r.stars)}</span>}
        {r.date_rel && <span className="review-date">{r.date_rel}</span>}
      </div>
      {r.text && <p className="review-text">{r.text}</p>}
      {r.photos.length > 0 && (
        <div className="review-photos">
          {r.photos.slice(0, 6).map((p, i) => (
            <img
              key={i}
              src={hiRes(p, "w400")}
              alt=""
              loading="lazy"
              onError={(e) => {
                e.currentTarget.style.display = "none";
              }}
            />
          ))}
        </div>
      )}
    </div>
  );
}

/** 迷你評分趨勢折線(inline SVG) */
function Trend({ points }: { points: (number | null)[] }) {
  const vals = points.filter((p): p is number => p != null);
  if (vals.length < 2) return null;
  const w = 240;
  const h = 40;
  const min = Math.min(...vals) - 0.05;
  const max = Math.max(...vals) + 0.05;
  const range = max - min || 1;
  const step = w / (vals.length - 1);
  const path = vals
    .map((v, i) => `${i === 0 ? "M" : "L"} ${(i * step).toFixed(1)} ${(h - ((v - min) / range) * h).toFixed(1)}`)
    .join(" ");
  return (
    <div>
      <svg width={w} height={h} style={{ maxWidth: "100%" }} aria-hidden>
        <path d={path} fill="none" stroke="var(--accent)" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round" />
      </svg>
      <div style={{ display: "flex", justifyContent: "space-between", fontSize: 12, color: "var(--fg-muted)", marginTop: 4 }}>
        <span>{vals[0].toFixed(2)}</span>
        <span style={{ color: statusColor("OPERATIONAL") }}>{vals[vals.length - 1].toFixed(2)}</span>
      </div>
    </div>
  );
}
