import { useEffect, useState } from "react";

type Theme = "light" | "dark";

function initialTheme(): Theme {
  try {
    const saved = localStorage.getItem("menmap-theme");
    if (saved === "light" || saved === "dark") return saved;
  } catch {
    /* localStorage 不可用時忽略 */
  }
  return window.matchMedia?.("(prefers-color-scheme: dark)").matches
    ? "dark"
    : "light";
}

export function useTheme() {
  const [theme, setTheme] = useState<Theme>(initialTheme);

  useEffect(() => {
    document.documentElement.setAttribute("data-theme", theme);
    try {
      localStorage.setItem("menmap-theme", theme);
    } catch {
      /* 忽略 */
    }
  }, [theme]);

  const toggle = () => setTheme((t) => (t === "dark" ? "light" : "dark"));
  return { theme, toggle };
}
