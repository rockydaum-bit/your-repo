// src/api/client.ts
import type {
  ChannelSummary,
  ChannelStatusSnapshot,
  RunRecord,
  AlertRecord,
  Publication,
  VersionInfo,
  WorkerStatus,
} from './types';

const BASE = '/api';

async function getJson<T>(url: string, options?: RequestInit): Promise<T> {
  const res = await fetch(url, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  });

  if (!res.ok) {
    const text = await res.text();
    throw new Error(`Request failed: ${res.status} ${res.statusText} – ${text}`);
  }

  // handle empty/no-content responses gracefully
  if (res.status === 204) {
    return {} as T;
  }

  const text = await res.text();
  if (!text) {
    return {} as T;
  }

  try {
    return JSON.parse(text) as T;
  } catch (err) {
    throw new Error(`Failed to parse JSON from ${url}: ${String(err)}`);
  }
}

export async function listChannels(): Promise<ChannelSummary[]> {
  return getJson<ChannelSummary[]>(`${BASE}/channels`);
}

export async function getChannelStatus(
  channelId: string,
): Promise<ChannelStatusSnapshot> {
  return getJson<ChannelStatusSnapshot>(
    `${BASE}/channels/${encodeURIComponent(channelId)}/status`,
  );
}

export async function listRuns(
  channelId: string,
  limit = 50,
): Promise<RunRecord[]> {
  return getJson<RunRecord[]>(
    `${BASE}/channels/${encodeURIComponent(channelId)}/runs?limit=${limit}`,
  );
}

export async function listAlerts(
  channelId: string,
  limit = 50,
): Promise<AlertRecord[]> {
  return getJson<AlertRecord[]>(
    `${BASE}/channels/${encodeURIComponent(channelId)}/alerts?limit=${limit}`,
  );
}

export async function fetchChannelPublications(
  channelId: string,
  limit = 50,
): Promise<Publication[]> {
  return getJson<Publication[]>(
    `${BASE}/channels/${encodeURIComponent(channelId)}/publications?limit=${limit}`,
  );
}

export async function fetchVersion(): Promise<VersionInfo> {
  return getJson<VersionInfo>(`${BASE}/version`);
}

export async function fetchWorkers(): Promise<WorkerStatus[]> {
  return getJson<WorkerStatus[]>(`${BASE}/workers`);
}

export async function triggerRun(channelId: string): Promise<{ run_id: string }> {
  return getJson<{ run_id: string }>(
    `${BASE}/channels/${encodeURIComponent(channelId)}/run`,
    { method: 'POST' },
  );
}

export async function triggerScore(channelId: string): Promise<{ run_id: string }> {
  return getJson<{ run_id: string }>(
    `${BASE}/channels/${encodeURIComponent(channelId)}/score`,
    { method: 'POST' },
  );
}
