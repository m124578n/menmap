import { useCallback, useEffect, useRef, useState } from "react";
import type { Shop } from "../types";

type Phase = "idle" | "rolling" | "result";

function pick(list: Shop[], not?: Shop | null): Shop {
  if (list.length === 1) return list[0];
  let s = list[Math.floor(Math.random() * list.length)];
  // 盡量不要連續骰到同一家(轉動時的視覺)
  let guard = 0;
  while (not && s.ftid === not.ftid && guard++ < 8)
    s = list[Math.floor(Math.random() * list.length)];
  return s;
}

/** 拉麵骰子:從 candidates 隨機選一家,附轉動動畫。 */
export function useDice(candidates: Shop[]) {
  const [phase, setPhase] = useState<Phase>("idle");
  const [display, setDisplay] = useState<Shop | null>(null);
  const candRef = useRef(candidates);
  candRef.current = candidates;
  const timers = useRef<number[]>([]);

  const clear = () => {
    timers.current.forEach((t) => clearTimeout(t));
    timers.current = [];
  };
  useEffect(() => clear, []);

  const roll = useCallback(() => {
    const list = candRef.current;
    if (list.length === 0) return;
    clear();
    setPhase("rolling");
    let current: Shop | null = null;
    // 轉動:間隔漸慢(80→220ms)共約 1 秒,最後定格
    const steps = [80, 80, 90, 100, 120, 150, 190, 220];
    let acc = 0;
    steps.forEach((d) => {
      acc += d;
      timers.current.push(
        window.setTimeout(() => {
          current = pick(candRef.current, current);
          setDisplay(current);
        }, acc)
      );
    });
    timers.current.push(
      window.setTimeout(() => {
        const final = pick(candRef.current, current);
        setDisplay(final);
        setPhase("result");
      }, acc + 260)
    );
  }, []);

  const reset = useCallback(() => {
    clear();
    setPhase("idle");
    setDisplay(null);
  }, []);

  return { phase, display, roll, reset, count: candidates.length };
}
