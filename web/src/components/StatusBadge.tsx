import type { BusinessStatus } from "../types";
import { statusColor, statusLabel } from "../lib/format";

export function StatusDot({ status }: { status: BusinessStatus }) {
  return <span className="dot" style={{ background: statusColor(status) }} />;
}

export function StatusBadge({ status }: { status: BusinessStatus }) {
  const color = statusColor(status);
  return (
    <span
      className="status-badge"
      style={{
        color,
        background: `color-mix(in srgb, ${color} 16%, transparent)`,
      }}
    >
      <span className="dot" style={{ background: color }} />
      {statusLabel(status)}
    </span>
  );
}
