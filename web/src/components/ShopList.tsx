import type { Shop } from "../types";
import { StatusDot } from "./StatusBadge";
import { formatCount } from "../lib/format";

interface Props {
  shops: Shop[];
  selected: string | null;
  onSelect: (ftid: string) => void;
}

function ShopCard({
  shop,
  selected,
  onSelect,
}: {
  shop: Shop;
  selected: boolean;
  onSelect: (ftid: string) => void;
}) {
  return (
    <button
      className="card"
      data-selected={selected}
      onClick={() => onSelect(shop.ftid)}
    >
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
          {shop.types[0] && <span className="tag">{shop.types[0]}</span>}
        </div>
      </div>
    </button>
  );
}

export default function ShopList({ shops, selected, onSelect }: Props) {
  if (shops.length === 0) {
    return <div className="empty">這個範圍/條件下沒有拉麵店<br />試試縮小地圖或清除篩選</div>;
  }
  return (
    <div className="list">
      {shops.map((s) => (
        <ShopCard
          key={s.ftid}
          shop={s}
          selected={s.ftid === selected}
          onSelect={onSelect}
        />
      ))}
    </div>
  );
}
