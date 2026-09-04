import { X, ExternalLink } from "lucide-react";

interface Props {
  onClose: () => void;
}

const REPO = "https://github.com/m124578n/menmap";

/** 關於本站:資料來源聲明、更新頻率、免責、回報管道。 */
export default function AboutOverlay({ onClose }: Props) {
  return (
    <div className="dice-overlay" onClick={onClose}>
      <div
        className="about-card panel noren-top"
        role="dialog"
        aria-modal="true"
        aria-label="關於本站"
        onClick={(e) => e.stopPropagation()}
      >
        <button className="close-btn" onClick={onClose} aria-label="關閉">
          <X size={18} />
        </button>
        <h2 className="about-title">
          <span className="stamp">麺</span> 關於雙北拉麵地圖
        </h2>
        <p className="about-lead">
          雙北拉麵店的互動地圖:營業狀態、營業時間、評分評論、菜單照片,
          外加一顆幫你決定今天吃哪間的拉麵骰子。個人專案,非商業用途。
        </p>

        <h3>資料來源</h3>
        <p>
          店家資料(名稱、地址、營業時間、評分、評論、照片、商家貼文)取自
          <strong> Google 地圖</strong>的公開頁面,每天自動更新一次。
          評論與照片的著作權屬原作者與 Google;本站僅整理與呈現,不擁有這些內容。
          點「在 Google 地圖開啟」可查看原始頁面。
        </p>

        <h3>更新頻率與準確度</h3>
        <ul>
          <li>營業狀態、評分、當日營業時間:<strong>每天更新</strong>(晚間)。</li>
          <li>評論、菜單照、商家貼文:每家店約<strong>每週</strong>輪替更新一次。</li>
          <li>新店、改名、搬家:<strong>每週日</strong>重新搜尋。</li>
          <li>
            「營業中」是依 Google 上的營業時間對當下時刻推算,店家臨時公休或調整不一定即時反映,
            出門前建議再確認店家公告。
          </li>
        </ul>

        <h3>免責聲明</h3>
        <p>
          本站與 Google 及各店家皆無關聯。資料可能有延遲或錯誤,依本站資訊所做的決定由使用者自行負責。
          若你是店家,希望修正或移除資訊,請透過下方管道聯絡。
        </p>

        <h3>回報錯誤 / 聯絡</h3>
        <p>
          發現店家資訊不對(搬家了、已歇業、時間不準)或有功能建議,歡迎到
          <a href={`${REPO}/issues`} target="_blank" rel="noreferrer">
            GitHub Issues <ExternalLink size={11} style={{ verticalAlign: "-1px" }} />
          </a>
          回報。原始碼在
          <a href={REPO} target="_blank" rel="noreferrer">
            {" "}GitHub <ExternalLink size={11} style={{ verticalAlign: "-1px" }} />
          </a>
          。
        </p>

        <p className="about-credits">
          地圖底圖 © <a href="https://carto.com/attributions" target="_blank" rel="noreferrer">CARTO</a>、
          © <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noreferrer">OpenStreetMap</a> 貢獻者。
          字型 Noto Sans TC / Noto Serif JP。本站不使用 cookie 追蹤。
        </p>
      </div>
    </div>
  );
}
