import { useEffect, useMemo, useState } from 'react';

import './styles.css';

interface SyncJob {
  api_name: string;
  status: string;
  cursor_value: string | null;
  last_success_at: string | null;
  updated_at: string;
  error_message: string | null;
}

interface ProblemRun {
  api_name: string;
  status: string;
  run_id: number;
  window_start: string | null;
  window_end: string | null;
  started_at: string;
  finished_at: string | null;
  error_message: string | null;
}

interface QualityAlert {
  api_name: string;
  status: string;
  severity: string;
  check_name: string;
  message: string | null;
  observed_value: string | null;
  created_at: string;
}

interface TableCount {
  name: string;
  rows: number;
}

interface SyncStatus {
  jobs: SyncJob[];
  problem_runs: ProblemRun[];
  quality_alerts: QualityAlert[];
  table_counts: TableCount[];
  retryable_failed_count: number;
  blocked_count: number;
}

const apiBaseUrl = String(import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000/api/v1');

export function App() {
  const [status, setStatus] = useState<SyncStatus | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function loadStatus(signal?: AbortSignal) {
    setLoading(true);
    setError(null);
    try {
      const response = await fetch(`${apiBaseUrl}/sync/tushare/status`, { signal });
      if (!response.ok) {
        throw new Error(`HTTP ${String(response.status)}`);
      }
      setStatus((await response.json()) as SyncStatus);
    } catch (loadError) {
      if (loadError instanceof DOMException && loadError.name === 'AbortError') {
        return;
      }
      setError(loadError instanceof Error ? loadError.message : 'Unknown error');
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    const controller = new AbortController();
    void loadStatus(controller.signal);
    return () => {
      controller.abort();
    };
  }, []);

  const totals = useMemo(() => {
    const jobs = status?.jobs ?? [];
    return {
      success: jobs.filter((job) => job.status === 'success').length,
      failed: jobs.filter((job) => job.status === 'failed').length,
      blocked: jobs.filter((job) => job.status === 'blocked_insufficient_points').length,
      running: jobs.filter((job) => job.status === 'running').length,
    };
  }, [status]);

  return (
    <main className="app-shell">
      <header className="topbar">
        <div>
          <p className="eyebrow">Fun Stock</p>
          <h1>Tushare 数据同步</h1>
        </div>
        <button className="refresh-button" type="button" onClick={() => void loadStatus()}>
          {loading ? '刷新中' : '刷新'}
        </button>
      </header>

      {error ? <p className="error-banner">后端状态读取失败：{error}</p> : null}

      <section className="metric-grid" aria-label="同步概览">
        <Metric label="成功接口" value={totals.success} tone="success" />
        <Metric label="失败接口" value={status?.retryable_failed_count ?? totals.failed} tone="danger" />
        <Metric label="阻塞接口" value={status?.blocked_count ?? totals.blocked} tone="warning" />
        <Metric label="运行中" value={totals.running} tone="neutral" />
      </section>

      <section className="content-grid">
        <div className="panel wide">
          <div className="panel-heading">
            <h2>接口状态</h2>
            <span>{status?.jobs.length ?? 0} 个接口</span>
          </div>
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>接口</th>
                  <th>状态</th>
                  <th>游标</th>
                  <th>最近成功</th>
                  <th>更新时间</th>
                </tr>
              </thead>
              <tbody>
                {(status?.jobs ?? []).slice(0, 30).map((job) => (
                  <tr key={job.api_name}>
                    <td>{job.api_name}</td>
                    <td>
                      <StatusBadge status={job.status} />
                    </td>
                    <td>{job.cursor_value ?? '-'}</td>
                    <td>{formatTime(job.last_success_at)}</td>
                    <td>{formatTime(job.updated_at)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        <div className="panel">
          <div className="panel-heading">
            <h2>业务表</h2>
          </div>
          <div className="table-counts">
            {(status?.table_counts ?? []).map((table) => (
              <div className="count-row" key={table.name}>
                <span>{table.name}</span>
                <strong>{table.rows.toLocaleString('zh-CN')}</strong>
              </div>
            ))}
          </div>
        </div>

        <div className="panel">
          <div className="panel-heading">
            <h2>质量告警</h2>
            <span>{status?.quality_alerts.length ?? 0}</span>
          </div>
          <div className="event-list">
            {(status?.quality_alerts ?? []).map((alert) => (
              <article className="event-item" key={`${alert.api_name}-${alert.check_name}-${alert.created_at}`}>
                <div>
                  <strong>{alert.api_name}</strong>
                  <span>{alert.check_name}</span>
                </div>
                <p>{alert.message ?? '-'}</p>
              </article>
            ))}
          </div>
        </div>

        <div className="panel wide">
          <div className="panel-heading">
            <h2>最近失败记录</h2>
            <span>{status?.problem_runs.length ?? 0}</span>
          </div>
          <div className="event-list dense">
            {(status?.problem_runs ?? []).map((run) => (
              <article className="event-item" key={run.run_id}>
                <div>
                  <strong>{run.api_name}</strong>
                  <StatusBadge status={run.status} />
                </div>
                <p>{run.error_message ?? '-'}</p>
              </article>
            ))}
          </div>
        </div>
      </section>
    </main>
  );
}

function Metric(props: { label: string; value: number; tone: string }) {
  return (
    <div className="metric" data-tone={props.tone}>
      <span>{props.label}</span>
      <strong>{props.value}</strong>
    </div>
  );
}

function StatusBadge(props: { status: string }) {
  return (
    <span className="status-badge" data-status={props.status}>
      {props.status}
    </span>
  );
}

function formatTime(value: string | null) {
  if (!value) {
    return '-';
  }
  return new Intl.DateTimeFormat('zh-CN', {
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  }).format(new Date(value));
}
