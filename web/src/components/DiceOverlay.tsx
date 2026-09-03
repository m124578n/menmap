import { Dices, X } from "lucide-react";
import type { Shop } from "../types";

interface Props {
  phase: "rolling" | "result";
  shop: Shop | null;
  onChoose: (ftid: string) => void;
  onReroll: () => void;
  onClose: () => void;
}

export default function DiceOverlay({ phase, shop, onChoose, onReroll, onClose }: Props) {
  return (
    <div className="dice-overlay" onClick={onClose}>
      <div className="dice-card panel noren-top" onClick={(e) => e.stopPropagation()}>
        <button className="close-btn" onClick={onClose} aria-label="關閉">
          <X size={18} />
        </button>

        <div className={`dice-emoji ${phase === "rolling" ? "spin" : ""}`}>
          <Dices size={40} />
        </div>

        <div className="dice-label">
          {phase === "rolling" ? "拉麵骰子轉動中…" : "今天就吃這間!"}
        </div>

        <div className="dice-name" data-rolling={phase === "rolling"}>
          {shop?.name ?? "—"}
        </div>

        {phase === "result" && shop && (
          <div className="dice-meta">
            {[shop.district].filter(Boolean).join(" ")}
            {shop.rating != null && <span> · ★ {shop.rating.toFixed(1)}</span>}
            {shop.price && <span> · {shop.price}</span>}
          </div>
        )}

        {phase === "result" && (
          <div className="dice-actions">
            <button className="dice-btn secondary" onClick={onReroll}>
              再骰一次
            </button>
            <button
              className="dice-btn primary"
              onClick={() => shop && onChoose(shop.ftid)}
            >
              看這間
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
