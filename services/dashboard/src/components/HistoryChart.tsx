import React, { useEffect, useState } from "react";
import { IoTNode, MeasurementPoint } from "../types/iot";

interface Props {
  node: IoTNode | null;
  onClose: () => void;
}

export const HistoryChart: React.FC<Props> = ({ node, onClose }) => {
  const [points, setPoints] = useState<MeasurementPoint[]>([]);

  useEffect(() => {
    if (!node) return;
    fetch(`/api/nodes/${node.node_id}/history?limit=30`)
      .then((r) => r.json())
      .then(setPoints)
      .catch(() => setPoints([]));
  }, [node]);

  if (!node) return null;

  const temps = points.map((p) => p.temperature_c);
  const minT = temps.length ? Math.min(...temps) - 1 : 15;
  const maxT = temps.length ? Math.max(...temps) + 1 : 30;
  const span = Math.max(1, maxT - minT);

  const svgPoints = points
    .map((p, i) => {
      const x = points.length > 1 ? (i / (points.length - 1)) * 560 + 20 : 300;
      const y = 140 - ((p.temperature_c - minT) / span) * 110;
      return `${x},${y}`;
    })
    .join(" ");

  return (
    <div
      style={{
        position: "fixed",
        inset: 0,
        background: "rgba(0,0,0,0.7)",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        zIndex: 50,
      }}
      onClick={onClose}
    >
      <div
        style={{
          background: "#1e293b",
          border: "1px solid #475569",
          borderRadius: "12px",
          padding: "24px",
          width: "660px",
          maxWidth: "95vw",
          maxHeight: "85vh",
          overflowY: "auto",
        }}
        onClick={(e) => e.stopPropagation()}
      >
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "16px" }}>
          <h3 style={{ margin: 0 }}>
            Historique — {node.node_id} ({node.network.toUpperCase()})
          </h3>
          <button
            onClick={onClose}
            style={{ background: "#334155", color: "#fff", border: "none", borderRadius: "6px", padding: "6px 12px", cursor: "pointer" }}
          >
            Fermer
          </button>
        </div>

        {points.length === 0 ? (
          <p style={{ color: "#94a3b8" }}>Aucune mesure enregistrée pour le moment.</p>
        ) : (
          <>
            <div style={{ background: "#0f172a", borderRadius: "8px", padding: "12px", marginBottom: "16px" }}>
              <div style={{ fontSize: "12px", color: "#94a3b8", marginBottom: "6px" }}>
                Évolution de la température (°C) — min {minT.toFixed(1)}°C / max {maxT.toFixed(1)}°C
              </div>
              <svg viewBox="0 0 600 160" style={{ width: "100%", height: "160px" }}>
                <polyline fill="none" stroke="#38bdf8" strokeWidth="2.5" points={svgPoints} />
                {points.map((p, i) => {
                  const x = points.length > 1 ? (i / (points.length - 1)) * 560 + 20 : 300;
                  const y = 140 - ((p.temperature_c - minT) / span) * 110;
                  return <circle key={i} cx={x} cy={y} r="3.5" fill="#38bdf8" />;
                })}
              </svg>
            </div>

            <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "13px" }}>
              <thead>
                <tr style={{ borderBottom: "1px solid #334155", textAlign: "left", color: "#94a3b8" }}>
                  <th style={{ padding: "6px" }}>Horodatage</th>
                  <th style={{ padding: "6px" }}>Temp.</th>
                  <th style={{ padding: "6px" }}>Hum.</th>
                  <th style={{ padding: "6px" }}>Pression</th>
                  <th style={{ padding: "6px" }}>Batt.</th>
                </tr>
              </thead>
              <tbody>
                {[...points].reverse().slice(0, 12).map((p, idx) => (
                  <tr key={idx} style={{ borderBottom: "1px solid #1e293b" }}>
                    <td style={{ padding: "6px" }}>{new Date(p.timestamp).toLocaleTimeString()}</td>
                    <td style={{ padding: "6px" }}>{p.temperature_c.toFixed(2)} °C</td>
                    <td style={{ padding: "6px" }}>{p.humidity_pct.toFixed(1)} %</td>
                    <td style={{ padding: "6px" }}>{p.pressure_hpa.toFixed(1)} hPa</td>
                    <td style={{ padding: "6px" }}>{p.battery_pct} %</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </>
        )}
      </div>
    </div>
  );
};