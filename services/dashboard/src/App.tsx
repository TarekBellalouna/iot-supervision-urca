import React, { useEffect, useState } from "react";
import { CountersBar } from "./components/CountersBar";
import { HistoryChart } from "./components/HistoryChart";
import { NodeCard } from "./components/NodeCard";
import { QueryModal } from "./components/QueryModal";
import { useEventStream } from "./hooks/useEventStream";
import { IoTNode, PlatformCounters, QueryRecord, RejectionLog } from "./types/iot";

export default function App() {
  const [nodes, setNodes] = useState<Record<string, IoTNode>>({});
  const [counters, setCounters] = useState<PlatformCounters>({
    received_count: 0,
    rejected_count: 0,
    deduplicated_count: 0,
  });
  const [queries, setQueries] = useState<QueryRecord[]>([]);
  const [rejections, setRejections] = useState<RejectionLog[]>([]);
  const [selectedHistoryNode, setSelectedHistoryNode] = useState<IoTNode | null>(null);
  const [queryingIds, setQueryingIds] = useState<Record<string, boolean>>({});

  // Chargement initial de l'état depuis l'API REST
  useEffect(() => {
    fetch("/api/nodes")
      .then((r) => r.json())
      .then((list: IoTNode[]) => {
        const map: Record<string, IoTNode> = {};
        list.forEach((n) => (map[n.node_id] = n));
        setNodes(map);
      });

    fetch("/api/counters").then((r) => r.json()).then(setCounters);
    fetch("/api/queries").then((r) => r.json()).then(setQueries);
    fetch("/api/rejections").then((r) => r.json()).then(setRejections);
  }, []);

  // Abonnement temps réel SSE
  const { connected } = useEventStream({
    onNodeUpdate: (updated) => {
      setNodes((prev) => ({ ...prev, [updated.node_id]: updated }));
    },
    onCountersUpdate: (c) => setCounters(c),
    onQueryUpdate: (q) => {
      setQueries((prev) => {
        const idx = prev.findIndex((item) => item.query_id === q.query_id);
        if (idx >= 0) {
          const copy = [...prev];
          copy[idx] = q;
          return copy;
        }
        return [q, ...prev];
      });
      if (q.status === "succeeded" || q.status === "expired") {
        setQueryingIds((prev) => ({ ...prev, [q.node_id]: false }));
      }
    },
    onRejectionAlert: (alert) => {
      setRejections((prev) => [
        {
          id: Date.now(),
          node_id: alert.node_id,
          network: alert.network,
          timestamp: new Date().toISOString(),
          reason: alert.reason,
        },
        ...prev.slice(0, 14),
      ]);
    },
  });

  const handleQueryNode = async (nodeId: string) => {
    setQueryingIds((prev) => ({ ...prev, [nodeId]: true }));
    try {
      await fetch(`/api/nodes/${nodeId}/query`, { method: "POST" });
    } catch {
      setQueryingIds((prev) => ({ ...prev, [nodeId]: false }));
    }
  };

  const sortedNodes = Object.values(nodes).sort((a, b) =>
    `${a.network}-${a.node_id}`.localeCompare(`${b.network}-${b.node_id}`)
  );

  return (
    <div style={{ maxWidth: "1360px", margin: "0 auto", padding: "24px" }}>
      <header style={{ marginBottom: "24px" }}>
        <h1 style={{ margin: 0, fontSize: "24px" }}>Supervision IoT Multi-Réseaux — Master 2 DAS</h1>
        <p style={{ margin: "6px 0 0 0", color: "#94a3b8", fontSize: "14px" }}>
          LoRaWAN (ChirpStack v4) • Zigbee (ZCL / MQTT) • Thread (IPv6 / CoAP)
        </p>
      </header>

      <CountersBar counters={counters} sseConnected={connected} />

      <QueryModal queries={queries} />

      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fill, minmax(310px, 1fr))",
          gap: "16px",
          marginBottom: "28px",
        }}
      >
        {sortedNodes.map((n) => (
          <NodeCard
            key={n.node_id}
            node={n}
            onQuery={handleQueryNode}
            onSelectHistory={setSelectedHistoryNode}
            isQuerying={!!queryingIds[n.node_id]}
          />
        ))}
      </div>

      {/* Journal des rejets hors plage */}
      {rejections.length > 0 && (
        <div
          style={{
            background: "#1e293b",
            border: "1px solid #7f1d1d",
            borderRadius: "12px",
            padding: "16px",
          }}
        >
          <h3 style={{ margin: "0 0 10px 0", fontSize: "15px", color: "#fca5a5" }}>
            Dernières mesures hors plage rejetées
          </h3>
          {rejections.slice(0, 5).map((r) => (
            <div key={r.id} style={{ fontSize: "13px", padding: "4px 0", color: "#fecaca" }}>
              [{new Date(r.timestamp).toLocaleTimeString()}] <strong>{r.node_id}</strong> ({r.network}) : {r.reason}
            </div>
          ))}
        </div>
      )}

      <HistoryChart node={selectedHistoryNode} onClose={() => setSelectedHistoryNode(null)} />
    </div>
  );
}