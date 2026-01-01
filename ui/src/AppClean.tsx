import { useEffect, useState } from 'react';
import { fetchVersion, listChannels } from './api/client';

export default function AppClean() {
  const [version, setVersion] = useState<any | null>(null);
  const [channels, setChannels] = useState<any[]>([]);

  useEffect(() => {
    (async () => {
      try {
        const v = await fetchVersion();
        setVersion(v);
      } catch {}
      try {
        const ch = await listChannels();
        setChannels(ch ?? []);
      } catch {}
    })();
  }, []);

  return (
    <div style={{ padding: 20, fontFamily: 'system-ui, sans-serif' }}>
      <h1>Autonomous Media Engine Console</h1>
      <div style={{ marginTop: 8, color: '#555' }}>{version ? `v${version.version} · ${version.role}` : 'Loading version...'}</div>
      <h2 style={{ marginTop: 16 }}>Channels</h2>
      <ul>
        {channels.map((c: any) => (
          <li key={c.channel_id}>{c.name ?? c.channel_id}</li>
        ))}
      </ul>
    </div>
  );
}
