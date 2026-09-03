import { Component, StrictMode, type ReactNode } from "react";
import { createRoot } from "react-dom/client";
import "maplibre-gl/dist/maplibre-gl.css";
import "./styles/tokens.css";
import "./styles/app.css";
import App from "./App";

/** 最外層錯誤邊界:任何 render 期例外都不會讓整頁變白。 */
class ErrorBoundary extends Component<{ children: ReactNode }, { error: Error | null }> {
  state = { error: null as Error | null };
  static getDerivedStateFromError(error: Error) {
    return { error };
  }
  render() {
    if (this.state.error) {
      return (
        <div className="fatal">
          <h1>頁面發生錯誤</h1>
          <p>重新整理通常就能解決。若持續發生,請稍後再試。</p>
          <button className="dice-btn primary" onClick={() => window.location.reload()}>
            重新整理
          </button>
        </div>
      );
    }
    return this.props.children;
  }
}

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <ErrorBoundary>
      <App />
    </ErrorBoundary>
  </StrictMode>
);
