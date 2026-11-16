import React from "react";
import { QueryRecord } from "../types/iot";

interface Props {
  queries: QueryRecord[];
}

const STATE_LABELS: Record<string, { text: string; color: string }> = {
  sent: { text: "Envoyée", color: "#38bdf8" },
  pending: { text: "En attente...", color: "#fbbf24" },
  succeeded: { text: "Réussie", color: "#4ade80" },
  expired: { text: "Expirée", color: "#f87171" },
};

export const QueryModal: React.FC<Props> = ({ queries }) => {
  if (queries.length === 0) return null;

  return (
    <div
      style={{
        background: "#1e293b",
        border: "1px solid #334155",
        borderRadius: "12px",
        padding: "16px",
        marginBottom: "24px",
      }}
    >
      <h3 style={{ margin: "0 0 12px 0", fontSize: "15px" }}>Journal des interrogations à la demande</h3>
      <div style={{ display: "flex", flexDirection: "column", gap: "8px" }}>
        {queries.slice(0, 6).map((q) => {
          const badge = STATE_LABELS[q.status] || { text: q.status, color: "#94a3b8" };
          return (
            <div
              key={q.query_id}
              style={{
                display: "flex",
                justifyContent: "space-between",
                alignItems: "center",
                background: "#0f172a",
                padding: "8px 12px",
                borderRadius: "8px",
                fontSize: "13px",
              }}
            >
              <div>
                <strong>{q.node_id}</strong> ({q.network.toUpperCase()}) —{" "}
                <span style={{ color: "#cbd5e1" }}>{q.detail}</span>
              </div>
              <span style={{ fontWeight: 700, color: badge.color, marginLeft: "12px", whiteSpace: "nowrap" }}>
                {badge.text}
              </span>
            </div>
          );
        })}
      </div>
    </div>
  );
};