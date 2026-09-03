import type { BusinessStatus } from "../types";

export const STATUS_LABEL: Record<string, string> = {
  OPERATIONAL: "營業中",
  CLOSED_TEMPORARILY: "暫停營業",
  CLOSED_PERMANENTLY: "永久停業",
};

export function statusLabel(s: BusinessStatus): string {
  return s ? STATUS_LABEL[s] ?? "狀態不明" : "狀態不明";
}

// 標記/徽章用色(明暗底圖皆可讀)
export const STATUS_COLOR: Record<string, string> = {
  OPERATIONAL: "#2e9e6b",
  CLOSED_TEMPORARILY: "#d9922b",
  CLOSED_PERMANENTLY: "#c6402f",
  UNKNOWN: "#8a8072",
};

export function statusColor(s: BusinessStatus): string {
  return s ? STATUS_COLOR[s] ?? STATUS_COLOR.UNKNOWN : STATUS_COLOR.UNKNOWN;
}

export function stars(rating: number | null): string {
  if (rating == null) return "";
  const full = Math.round(rating);
  return "★".repeat(full) + "☆".repeat(Math.max(0, 5 - full));
}

/**
 * 放大 Google 相片解析度。
 * googleusercontent/ggpht 圖片 URL 尾端的 `=w129-h86-k-no` 是尺寸指令,
 * 換成較大的尺寸即可拿到清晰圖(採集端存的是縮圖,顯示時才放大,不破壞來源)。
 */
export function hiRes(url: string | null | undefined, spec = "w1000"): string {
  if (!url) return "";
  if (!/googleusercontent\.com|ggpht\.com/.test(url)) return url;
  // 尾端有 `=...` 尺寸指令就取代;沒有就補上
  return /=[\w-]+$/.test(url) ? url.replace(/=[\w-]+$/, `=${spec}`) : `${url}=${spec}`;
}

export function formatCount(n: number | null): string {
  if (n == null) return "";
  if (n >= 10000) return `${(n / 10000).toFixed(1)}萬`;
  if (n >= 1000) return `${(n / 1000).toFixed(1)}k`;
  return String(n);
}
