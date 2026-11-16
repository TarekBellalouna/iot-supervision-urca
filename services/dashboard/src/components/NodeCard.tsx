import React from "react";
import { IoTNode } from "../types/iot";

interface Props {
  node: IoTNode;
  onQuery: (nodeId: string) => void;
  onSelectHistory: (node: IoTNode) => void;
  isQuerying: boolean;
}

const STATUS_META: Record<string, { label: string; bg: string; color: string }> = {
  online: { label: "En ligne", bg: "rgba(34, 197, 94, 0.15)", color: "#4ade80" },
  delayed: { label: "En retard", bg: "rgba(250, 204, 21, 0.15)", color: "#facc15" },
  lost: { label: "Perdu", bg: "rgba(239, 68, 68, 0.15)", color: "#f87171" },
  offline: { label: "Hors ligne", bg: "rgba(148, 163, 184, 0.15)", color: "#94a3b8" },
};

const NETWORK_BADGE: Record<string, string> = {
  lorawan: "#a855f7",
  zigbee: "#f97316",
  thread: "#06b6d4",
};

export const NodeCard: React.FC<Props> = ({ node, onQuery, onSelectHistory, isQuerying }) => {
  const st = STATUS_META[node.status] || STATUS_META.offline;
  const netColor = NETWORK_BADGE[node.network] || "#64748b";

  return (
    <div
      style={{
        background: "#1e293b",
        border: "1px solid #334155",
        borderRadius: "12px",
        padding: "16px",
        display: "flex",
        flexDirection: "column",
        gap: "12px",
      }}
    >
      {/* En-tête : Réseau + Identifiant + État */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
          <span
            style={{
              background: netColor,
              color: "#fff",
              fontSize: "11px",
              fontWeight: 700,
              padding: "2px 8px",
              borderRadius: "6px",
              textTransform: "uppercase",
            }}
          >
            {node.network}
          </span>
          <strong style={{ fontSize: "16px" }}>{node.node_id}</strong>
        </div>

        <span
          style={{
            background: st.bg,
            color: st.color,
            fontSize: "12px",
            fontWeight: 600,
            padding: "3px 10px",
            borderRadius: "999px",
          }}
        >
          {st.label}
        </span>
      </div>

      {/* Identifiant natif et rôle */}
      <div style={{ fontSize: "12px", color: "#94a3b8", fontFamily: "monospace" }}>
        ID: {node.native_id} • Rôle: {node.role}
      </div>

      {/* Dernières mesures */}
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(2, 1fr)",
          gap: "8px",
          background: "#0f172a",
          padding: "10px",
          borderRadius: "8px",
          fontSize: "13px",
        }}
      >
        <div>
          <span style={{ color: "#94a3b8" }}>Temp : </span>
          <strong>{node.temperature_c !== null && node.temperature_c !== undefined ? `${node.temperature_c.toFixed(1)} °C` : "—"}</strong>
        </div>
        <div>
          <span style={{ color: "#94a3b8" }}>Humidité : </span>
          <strong>{node.humidity_pct !== null && node.humidity_pct !== undefined ? `${node.humidity_pct.toFixed(1)} %` : "—"}</strong>
        </div>
        <div>
          <span style={{ color: "#94a3b8" }}>Pression : </span>
          <strong>{node.pressure_hpa !== null && node.pressure_hpa !== undefined ? `${node.pressure_hpa.toFixed(1)} hPa` : "—"}</strong>
        </div>
        <div>
          <span style={{ color: "#94a3b8" }}>Batterie : </span>
          <strong>{node.battery_pct !== null && node.battery_pct !== undefined ? `${node.battery_pct} %` : "—"}</strong>
        </div>
      </div>

      {/* Âge de la donnée et qualité de liaison radio */}
      <div style={{ display: "flex", justifyContent: "space-between", fontSize: "12px", color: "#cbd5e1" }}>
        <span>
          Âge : <strong>{node.age_seconds !== null && node.age_seconds !== undefined ? `${node.age_seconds.toFixed(0)} s` : "Jamais reçu"}</strong>
        </span>
        <span>
          {node.rssi_dbm !== null && node.rssi_dbm !== undefined
            ? `RSSI ${node.rssi_dbm} dBm | SNR ${node.snr_db ?? "—"} dB`
            : node.link_quality !== null && node.link_quality !== undefined
            ? `LQI ${node.link_quality}/255`
            : "Lien radio : —"}
        </span>
      </div>

      {/* Actions : Interrogation à la demande & Historique */}
      <div style={{ display: "flex", gap: "8px", marginTop: "4px" }}>
        <button
          onClick={() => onQuery(node.node_id)}
          disabled={isQuerying}
          style={{
            flex: 1,
            background: isQuerying ? "#475569" : "#2563eb",
            color: "#fff",
            border: "none",
            borderRadius: "8px",
            padding: "8px 12px",
            fontWeight: 600,
            cursor: isQuerying ? "wait" : "pointer",
          }}
        >
          {isQuerying ? "En cours..." : "Interroger"}
        </button>

        <button
          onClick={() => onSelectHistory(node)}
          style={{
            background: "#334155",
            color: "#f8fafc",
            border: "none",
            borderRadius: "8px",
            padding: "8px 12px",
            cursor: "pointer",
          }}
        >
          Historique
        </button>
      </div>
    </div>
  );
};