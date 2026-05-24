import { useEffect, useState } from 'react';

import './styles.css';

interface ApiHealth {
  status: string;
  service: string;
}

const apiBaseUrl = String(import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000/api/v1');

export function App() {
  const [health, setHealth] = useState<ApiHealth | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const controller = new AbortController();

    async function loadHealth() {
      try {
        const response = await fetch(`${apiBaseUrl}/health`, {
          signal: controller.signal,
        });

        if (!response.ok) {
          throw new Error(`Unexpected response: ${String(response.status)}`);
        }

        setHealth((await response.json()) as ApiHealth);
      } catch (loadError) {
        if (loadError instanceof DOMException && loadError.name === 'AbortError') {
          return;
        }

        setError(loadError instanceof Error ? loadError.message : 'Unknown error');
      }
    }

    void loadHealth();

    return () => {
      controller.abort();
    };
  }, []);

  return (
    <main className="app-shell">
      <section className="workspace">
        <div>
          <p className="eyebrow">Fun Stock</p>
          <h1>股票策略研究工作台</h1>
          <p className="summary">工程基线已就绪，下一步可以开始接入数据模型和 Tushare 同步。</p>
        </div>

        <div className="status-panel" aria-label="Backend health status">
          <span className="status-dot" data-state={health?.status ?? 'loading'} />
          <div>
            <p className="status-title">Backend API</p>
            <p className="status-value">
              {health ? `${health.service}: ${health.status}` : (error ?? 'checking...')}
            </p>
          </div>
        </div>
      </section>
    </main>
  );
}
