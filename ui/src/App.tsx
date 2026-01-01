import { useEffect, useState } from 'react';
import { fetchVersion, listChannels } from './api/client';

function App() {
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

export default App;
import { useEffect, useState } from 'react';
import { fetchVersion, listChannels } from './api/client';

function App() {
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

export default App;

        <div style={{ display: 'flex', gap: '16px' }}>
          {/* Runs */}
          <div style={{ flex: 2 }}>
            <h3>Recent Runs</h3>
            <table style={{ width: '100%', borderCollapse: 'collapse' }}>
              <thead>
                <tr>
                  <th align="left">Start</th>
                  <th align="left">Mode</th>
                  <th align="left">Status</th>
                  <th align="left">Error</th>
                </tr>
              </thead>
              <tbody>
                {runs.map((r) => (
                  <tr key={r.run_id}>
                    <td>{r.ts_start}</td>
                    <td>{r.mode}</td>
                    <td>{r.status}</td>
                    <td style={{ color: '#a00', fontSize: '0.85rem' }}>
                      {r.error_message}
                    </td>
                  </tr>
                ))}
                {runs.length === 0 && (
                  <tr>
                    <td colSpan={4}>No runs yet.</td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>

          {/* Alerts */}
          <div style={{ flex: 1 }}>
            <h3>Recent Alerts</h3>
            <ul style={{ listStyle: 'none', padding: 0, margin: 0 }}>
              {alerts.map((a) => (
                <li
                  key={a.id}
                  style={{
                    marginBottom: '8px',
                    padding: '8px',
                    borderRadius: '6px',
                    border: '1px solid #ddd',
                    backgroundColor:
                      a.severity === 'error'
                        ? '#ffe5e5'
                        : a.severity === 'warning'
                        ? '#fff7e0'
                        : '#f5f5f5',
                  }}
                >
                  <div style={{ fontSize: '0.8rem', color: '#666' }}>
                    {a.ts} · {a.code}
                  </div>
                  <div>{a.message}</div>
                </li>
              ))}
              {alerts.length === 0 && <li>No alerts.</li>}
            </ul>
          </div>

          {/* Publications */}
          <div style={{ flex: 1 }}>
            <h3>Publications</h3>
            {publications.length === 0 ? (
              <div className="text-sm text-gray-500">No publications yet.</div>
            ) : (
              <div style={{ overflowX: 'auto', border: '1px solid #ddd', borderRadius: 6 }}>
                <table style={{ minWidth: '100%', fontSize: '0.9rem', borderCollapse: 'collapse' }}>
                  <thead style={{ background: '#fafafa' }}>
                    <tr>
                      <th style={{ textAlign: 'left', padding: '6px 8px' }}>Platform</th>
                      <th style={{ textAlign: 'left', padding: '6px 8px' }}>Video ID</th>
                      <th style={{ textAlign: 'left', padding: '6px 8px' }}>External ID</th>
                      <th style={{ textAlign: 'left', padding: '6px 8px' }}>Status</th>
                      <th style={{ textAlign: 'left', padding: '6px 8px' }}>Published</th>
                    </tr>
                  </thead>
                  <tbody>
                    {publications.map((pub) => (
                      <tr key={`${pub.platform}-${pub.video_id}`} style={{ borderTop: '1px solid #eee' }}>
                        <td style={{ padding: '6px 8px', whiteSpace: 'nowrap' }}>{formatPlatform(pub.platform)}</td>
                        <td style={{ padding: '6px 8px', whiteSpace: 'nowrap' }}>{pub.video_id}</td>
                        <td style={{ padding: '6px 8px', whiteSpace: 'nowrap' }}>
                          {pub.external_video_id && pub.platform === 'youtube' ? (
                            <a
                              href={`https://www.youtube.com/watch?v=${encodeURIComponent(
                                pub.external_video_id,
                              )}`}
                              target="_blank"
                              rel="noreferrer"
                              style={{ color: '#2563eb', textDecoration: 'underline' }}
                            >
                              {pub.external_video_id}
                            </a>
                          ) : pub.external_video_id ? (
                            pub.external_video_id
                          ) : (
                            '—'
                          )}
                        </td>
                        <td style={{ padding: '6px 8px', whiteSpace: 'nowrap' }}>{pub.status ?? 'unknown'}</td>
                        <td style={{ padding: '6px 8px', whiteSpace: 'nowrap' }}>{pub.published_ts ? new Date(pub.published_ts).toLocaleString() : '—'}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

export default App;
