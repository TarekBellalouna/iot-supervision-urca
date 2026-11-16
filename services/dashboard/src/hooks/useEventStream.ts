import { useEffect, useState } from "react";
import { IoTNode, PlatformCounters, QueryRecord } from "../types/iot";

interface StreamHandlers {
  onNodeUpdate: (node: IoTNode) => void;
  onCountersUpdate: (counters: PlatformCounters) => void;
  onQueryUpdate: (query: QueryRecord) => void;
  onRejectionAlert: (alert: {
    node_id: string;
    network: string;
    reason: string;
  }) => void;
}

export function useEventStream(handlers: StreamHandlers) {
  const [connected, setConnected] = useState(false);

  useEffect(() => {
    const es = new EventSource("/api/stream");

    es.addEventListener("connected", () => setConnected(true));
    es.onerror = () => setConnected(false);

    es.addEventListener("node_update", (ev) => {
      handlers.onNodeUpdate(JSON.parse((ev as MessageEvent).data));
    });

    es.addEventListener("counters_update", (ev) => {
      handlers.onCountersUpdate(JSON.parse((ev as MessageEvent).data));
    });

    es.addEventListener("query_update", (ev) => {
      handlers.onQueryUpdate(JSON.parse((ev as MessageEvent).data));
    });

    es.addEventListener("rejection_alert", (ev) => {
      handlers.onRejectionAlert(JSON.parse((ev as MessageEvent).data));
    });

    return () => {
      es.close();
    };
  }, []);

  return { connected };
}
