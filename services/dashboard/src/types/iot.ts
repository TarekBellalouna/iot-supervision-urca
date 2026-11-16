export type NetworkType = "lorawan" | "zigbee" | "thread";
export type NodeStatus = "online" | "delayed" | "lost" | "offline";
export type QueryStatus = "sent" | "pending" | "succeeded" | "expired";

export interface IoTNode {
  node_id: string;
  network: NetworkType;
  native_id: string;
  role: string;
  ipv6_address?: string | null;
  expected_interval_s: number;
  last_seen?: string | null;
  age_seconds?: number | null;
  status: NodeStatus;
  temperature_c?: number | null;
  humidity_pct?: number | null;
  pressure_hpa?: number | null;
  battery_pct?: number | null;
  rssi_dbm?: number | null;
  snr_db?: number | null;
  link_quality?: number | null;
  extra_meta: Record<string, unknown>;
}

export interface PlatformCounters {
  received_count: number;
  rejected_count: number;
  deduplicated_count: number;
}

export interface MeasurementPoint {
  timestamp: string;
  temperature_c: number;
  humidity_pct: number;
  pressure_hpa: number;
  battery_pct: number;
  rssi_dbm?: number | null;
  snr_db?: number | null;
}

export interface QueryRecord {
  query_id: string;
  node_id: string;
  network: NetworkType;
  status: QueryStatus;
  detail: string;
  created_at: string;
  updated_at: string;
}

export interface RejectionLog {
  id: number;
  node_id: string;
  network: string;
  timestamp: string;
  reason: string;
}
