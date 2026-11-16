import React from "react";
import { PlatformCounters } from "../types/iot";

interface Props {
  counters: PlatformCounters;
  sseConnected: boolean;
}

export const CountersBar: React.FC<Props> = ({ counters, sseConnected }) => {
  const cardStyle: React.CSSProperties = {
    background: "#1e293b",
    border: "1px solid #334155",
    borderRadius: "10px",
    padding: "16px 20px",
    flex: 1,
    minWidth: "180px",
  };

  return (
    <div style={{ display: "flex", gap: "16px", flexWrap: "wrap", marginBottom: "24px" }}>
      <div style={cardStyle}>
        <div style={{ fontSize: "12px", color: "#94a3b8", textTransform: "uppercase" }}>Messages valides reçus</div>
        <div style={{ fontSize: "28px", fontWeight: 700, color: "#38bdf8", marginTop: "4px" }}>
          {counters.received_count}
        </div>
      </div>

      <div style={cardStyle}>
        <div style={{ fontSize: "12px", color: "#94a3b8", textTransform: "uppercase" }}>Messages rejetés (hors plage)</div>
        <div style={{ fontSize: "28px", fontWeight: 700, color: "#f87171", marginTop: "4px" }}>
          {counters.rejected_count}
        </div>
      </div>

      <div style={cardStyle}>
        <div style={{ fontSize: "12px", color: "#94a3b8", textTransform: "uppercase" }}>Doublons écartés</div>
        <div style={{ fontSize: "28px", fontWeight: 700, color: "#fbbf24", marginTop: "4px" }}>
          {counters.deduplicated_count}
        </div>
      </div>

      <div style={cardStyle}>
        <div style={{ fontSize: "12px", color: "#94a3b8", textTransform: "uppercase" }}>Flux Temps Réel (SSE)</div>
        <div style={{ fontSize: "18px", fontWeight: 600, marginTop: "10px", color: sseConnected ? "#4ade80" : "#f87171" }}>
          {sseConnected ? "● Connecté" : "○ Reconnexion..."}
        </div>
      </div>
    </div>
  );
};