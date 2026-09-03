/** 營業時間判斷:現在營業中 / 深夜營業。
 *
 * hours 格式:[[星期名, ["11:00–04:00", ...]], ...]。
 * static 精簡版只有「當天」一筆(每日採集更新,隔日自動換);playwright 有整週。
 * 時段可跨午夜("11:00–04:00");也可能是「24 小時營業」之類文字。
 */

const WEEKDAYS = ["星期日", "星期一", "星期二", "星期三", "星期四", "星期五", "星期六"];

type Hours = [string, string[]][] | null | undefined;

function parseSpan(span: string): [number, number] | "allday" | null {
  if (span.includes("24")) return "allday";
  const m = span.match(/(\d{1,2}):(\d{2})\s*[–\-~]\s*(\d{1,2}):(\d{2})/);
  if (!m) return null;
  const start = +m[1] * 60 + +m[2];
  const end = +m[3] * 60 + +m[4];
  return [start, end];
}

function entryFor(hours: Hours, dayName: string): string[] | null {
  if (!hours) return null;
  const e = hours.find(([d]) => d === dayName);
  return e ? e[1] : null;
}

/** 現在是否營業中。null = 資料不足無法判斷。 */
export function isOpenNow(hours: Hours, now = new Date()): boolean | null {
  if (!hours || hours.length === 0) return null;
  const mins = now.getHours() * 60 + now.getMinutes();
  const today = WEEKDAYS[now.getDay()];
  const yesterday = WEEKDAYS[(now.getDay() + 6) % 7];

  const todaySpans = entryFor(hours, today);
  if (todaySpans) {
    for (const s of todaySpans) {
      const p = parseSpan(s);
      if (p === "allday") return true;
      if (!p) continue;
      const [start, end] = p;
      if (end > start) {
        if (mins >= start && mins < end) return true;
      } else if (mins >= start) {
        return true; // 跨午夜時段的「今天晚間」半段
      }
    }
  }
  // 昨天跨午夜的時段延伸到今天凌晨(如 11:00–04:00)
  const ySpans = entryFor(hours, yesterday);
  if (ySpans) {
    for (const s of ySpans) {
      const p = parseSpan(s);
      if (p && p !== "allday" && p[1] < p[0] && mins < p[1]) return true;
    }
  }
  // 只有單天資料且不是今天 → 無法判斷
  if (!todaySpans && hours.length <= 1) return null;
  return false;
}

/** 深夜營業:任一天打烊時間 ≥ 23:30 或跨午夜。 */
export function isLateNight(hours: Hours): boolean {
  if (!hours) return false;
  for (const [, spans] of hours) {
    for (const s of spans) {
      const p = parseSpan(s);
      if (p === "allday") return true;
      if (p && (p[1] < p[0] || p[1] >= 23 * 60 + 30)) return true;
    }
  }
  return false;
}
