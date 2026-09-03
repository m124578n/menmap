import { useCallback, useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { X, ZoomIn, ZoomOut, ChevronLeft, ChevronRight } from "lucide-react";
import { hiRes } from "../lib/format";

interface Props {
  photos: string[];
  index: number;
  onClose: () => void;
}

const MIN = 1;
const MAX = 5;
const STEP = 1.6;
const DBL_ZOOM = 2.5;

/**
 * 站內圖片燈箱:同一視窗浮現,不開新分頁。
 * - 關閉:右上 ×、Esc、點圖片以外的暗處
 * - 縮放:+/− 按鈕、滾輪、雙擊/雙點、兩指捏合;放大後可拖曳平移
 * - 多張:左右箭頭、← → 鍵
 */
export default function Lightbox({ photos, index: initial, onClose }: Props) {
  const [index, setIndex] = useState(initial);
  const [scale, setScale] = useState(1);
  const [tx, setTx] = useState(0);
  const [ty, setTy] = useState(0);
  const [dragging, setDragging] = useState(false);
  const [loaded, setLoaded] = useState(false);
  const closeRef = useRef<HTMLButtonElement>(null);
  // 進行中的指標(滑鼠/手指):pointerId → 座標
  const pointers = useRef(new Map<number, { x: number; y: number }>());
  const pinchStart = useRef<{ dist: number; scale: number } | null>(null);
  const moved = useRef(false); // 這次按下有沒有拖過(拖過就不當成「點暗處關閉」)
  const lastTap = useRef(0);

  const many = photos.length > 1;
  const src = hiRes(photos[index], "s1600");

  const reset = useCallback(() => {
    setScale(1);
    setTx(0);
    setTy(0);
  }, []);

  const zoomTo = useCallback((next: number) => {
    const s = Math.min(MAX, Math.max(MIN, next));
    setScale(s);
    if (s === 1) {
      setTx(0);
      setTy(0);
    }
  }, []);

  const go = useCallback(
    (delta: number) => {
      if (!many) return;
      setIndex((i) => (i + delta + photos.length) % photos.length);
      setLoaded(false);
      reset();
    },
    [many, photos.length, reset]
  );

  // 開啟:鎖住背景捲動、焦點移到關閉鈕;關閉時還原
  useEffect(() => {
    const prevOverflow = document.body.style.overflow;
    const prevFocus = document.activeElement as HTMLElement | null;
    document.body.style.overflow = "hidden";
    closeRef.current?.focus();
    return () => {
      document.body.style.overflow = prevOverflow;
      prevFocus?.focus?.();
    };
  }, []);

  // 鍵盤:capture 階段先攔,並 preventDefault 讓 App 的 Esc(關詳情)知道已被處理
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        e.preventDefault();
        onClose();
      } else if (e.key === "ArrowLeft") go(-1);
      else if (e.key === "ArrowRight") go(1);
      else if (e.key === "+" || e.key === "=") zoomTo(scale * STEP);
      else if (e.key === "-") zoomTo(scale / STEP);
    };
    window.addEventListener("keydown", onKey, true);
    return () => window.removeEventListener("keydown", onKey, true);
  }, [onClose, go, zoomTo, scale]);

  // 滾輪縮放:React 的 onWheel 是 passive,不能 preventDefault(會捲到背景),改掛原生非 passive 監聽
  const stageRef = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const el = stageRef.current;
    if (!el) return;
    const onWheel = (e: WheelEvent) => {
      e.preventDefault();
      setScale((s) => {
        const next = Math.min(MAX, Math.max(MIN, s * Math.exp(-e.deltaY * 0.0022)));
        if (next === 1) {
          setTx(0);
          setTy(0);
        }
        return next;
      });
    };
    el.addEventListener("wheel", onWheel, { passive: false });
    return () => el.removeEventListener("wheel", onWheel);
  }, []);

  const onPointerDown = (e: React.PointerEvent) => {
    (e.currentTarget as HTMLElement).setPointerCapture(e.pointerId);
    pointers.current.set(e.pointerId, { x: e.clientX, y: e.clientY });
    moved.current = false;
    if (pointers.current.size === 2) {
      const [a, b] = [...pointers.current.values()];
      pinchStart.current = { dist: Math.hypot(a.x - b.x, a.y - b.y), scale };
    } else if (scale > 1) {
      setDragging(true);
    }
  };

  const onPointerMove = (e: React.PointerEvent) => {
    const prev = pointers.current.get(e.pointerId);
    if (!prev) return;
    const cur = { x: e.clientX, y: e.clientY };
    pointers.current.set(e.pointerId, cur);

    if (pointers.current.size === 2 && pinchStart.current) {
      const [a, b] = [...pointers.current.values()];
      const dist = Math.hypot(a.x - b.x, a.y - b.y);
      zoomTo(pinchStart.current.scale * (dist / pinchStart.current.dist));
      moved.current = true;
      return;
    }
    if (pointers.current.size === 1 && scale > 1) {
      const dx = cur.x - prev.x;
      const dy = cur.y - prev.y;
      if (Math.abs(dx) + Math.abs(dy) > 2) moved.current = true;
      setTx((v) => v + dx);
      setTy((v) => v + dy);
    }
  };

  const onPointerUp = (e: React.PointerEvent) => {
    pointers.current.delete(e.pointerId);
    if (pointers.current.size < 2) pinchStart.current = null;
    if (pointers.current.size === 0) setDragging(false);
  };

  // 點暗處關閉;點圖片本身:雙擊/雙點切換放大
  const onStageClick = (e: React.MouseEvent) => {
    if (moved.current) return;
    if (e.target === e.currentTarget) {
      onClose();
      return;
    }
    const now = Date.now();
    if (now - lastTap.current < 320) {
      zoomTo(scale > 1 ? 1 : DBL_ZOOM);
      lastTap.current = 0;
    } else {
      lastTap.current = now;
    }
  };

  const ui = (
    <div className="lightbox" role="dialog" aria-modal="true" aria-label="圖片檢視">
      <div
        ref={stageRef}
        className="lightbox-stage"
        data-zoomed={scale > 1}
        data-dragging={dragging}
        onClick={onStageClick}
        onPointerDown={onPointerDown}
        onPointerMove={onPointerMove}
        onPointerUp={onPointerUp}
        onPointerCancel={onPointerUp}
      >
        <img
          className="lightbox-img"
          src={src}
          alt={`圖片 ${index + 1} / ${photos.length}`}
          draggable={false}
          data-loaded={loaded}
          onLoad={() => setLoaded(true)}
          style={{ transform: `translate(${tx}px, ${ty}px) scale(${scale})` }}
        />
        {!loaded && <div className="lightbox-spinner" aria-hidden="true" />}
      </div>

      {many && (
        <div className="lightbox-count">
          {index + 1} / {photos.length}
        </div>
      )}

      <div className="lightbox-bar">
        <button
          className="lightbox-btn"
          onClick={() => zoomTo(scale / STEP)}
          disabled={scale <= MIN}
          aria-label="縮小"
        >
          <ZoomOut size={18} />
        </button>
        <button
          className="lightbox-btn"
          onClick={() => zoomTo(scale * STEP)}
          disabled={scale >= MAX}
          aria-label="放大"
        >
          <ZoomIn size={18} />
        </button>
        <button ref={closeRef} className="lightbox-btn" onClick={onClose} aria-label="關閉">
          <X size={20} />
        </button>
      </div>

      {many && (
        <>
          <button className="lightbox-btn lightbox-nav prev" onClick={() => go(-1)} aria-label="上一張">
            <ChevronLeft size={22} />
          </button>
          <button className="lightbox-btn lightbox-nav next" onClick={() => go(1)} aria-label="下一張">
            <ChevronRight size={22} />
          </button>
        </>
      )}
    </div>
  );

  return createPortal(ui, document.body);
}
