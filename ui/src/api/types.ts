// src/api/types.ts

export type OverallStatus = 'ok' | 'degraded' | 'failing' | 'unknown';

export interface ChannelSummary {
  channel_id: string;
  name: string;
  overall_status: OverallStatus;
  last_run_ts: string | null;
  last_error: string | null;
}

export interface RunRecord {
  run_id: string;
  ts_start: string;
  ts_end: string | null;
  channel_id: string | null;
  mode: string;
  status: string;
  command: string | null;
  error_message: string | null;
}

export interface AlertRecord {
  id: number;
  ts: string;
  severity: 'info' | 'warning' | 'error';
  code: string;
  channel_id: string | null;
  run_id: string | null;
  message: string;
}

export interface ChannelStatusSnapshot {
  channel_id: string;
  overall_status: OverallStatus;
  latest_run: RunRecord | null;
  recent_alerts: AlertRecord[];
  metrics?: {
    recent_uploads?: number;
    last_7d_revenue_usd?: number;
    last_7d_views?: number;
  };
}

export type PublicationStatus = "published" | "upload_failed" | "draft" | "unknown";

export interface Publication {
  channel_id: string;
  video_id: string;
  platform: string;
  external_video_id: string | null;
  published_ts: string | null;
  status: PublicationStatus;
  metadata?: Record<string, unknown> | null;
}

export interface VersionInfo {
  version: string;
  role: string;
  mode: string;
  db_driver: string;
  storage_mode: string;
  engine_root: string;
  worker_id?: string | null;
}

export type WorkerStatus = {
  worker_id: string | null;
  last_heartbeat: string | null;
  last_status: string | null;
};
