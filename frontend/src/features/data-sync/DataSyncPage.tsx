import { useEffect, useMemo, useState } from 'react';

import { Metric } from '../../components/Metric';
import { StatusBadge } from '../../components/StatusBadge';
import { fetchTushareSyncStatus } from '../../services/apiClient';
import type { BackfillJob, SyncStatus } from '../../types/sync';

export function DataSyncPage() {
  const [status, setStatus] = useState<SyncStatus | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function loadStatus(signal?: AbortSignal) {
    setLoading(true);
    setError(null);
    try {
      setStatus(await fetchTushareSyncStatus(signal));
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
    const timer = window.setInterval(() => void loadStatus(), 30_000);
    return () => {
      controller.abort();
      window.clearInterval(timer);
    };
  }, []);

  const totals = useMemo(() => {
    const jobs = status?.jobs ?? [];
    return {
      blocked: jobs.filter((job) => job.status === 'blocked_insufficient_points').length,
      failed: jobs.filter((job) => job.status === 'failed').length,
      running: jobs.filter((job) => job.status === 'running').length,
      success: jobs.filter((job) => job.status === 'success').length,
    };
  }, [status]);

  const activeBackfillJob = useMemo<BackfillJob | null>(() => {
    const jobs = status?.backfill_jobs ?? [];
    const runningJob = jobs.find((job) => job.is_running);
    if (runningJob) {
      return runningJob;
    }
    return jobs.length > 0 ? jobs[0] : null;
  }, [status]);

  return (
    <>
      <header className="module-header">
        <div>
          <p className="eyebrow">Data Operations</p>
          <h1>数据同步</h1>
        </div>
        <button className="primary-button" type="button" onClick={() => void loadStatus()}>
          {loading ? '刷新中' : '刷新'}
        </button>
      </header>

      {error ? <p className="error-banner">后端状态读取失败：{error}</p> : null}

      <section className="metric-grid" aria-label="同步概览">
        <Metric label="成功接口" value={totals.success} tone="success" />
        <Metric label="失败接口" value={status?.retryable_failed_count ?? totals.failed} tone="danger" />
        <Metric label="阻塞接口" value={status?.blocked_count ?? totals.blocked} tone="warning" />
        <Metric label="缺口交易日" value={status?.core_completeness.total_missing_trade_days ?? 0} tone="neutral" />
      </section>

      {activeBackfillJob ? <BackfillConsole job={activeBackfillJob} /> : null}

      <section className="content-grid">
        <div className="panel">
          <div className="panel-heading">
            <h2>核心表完整性</h2>
            <span>{status?.core_completeness.exchange ?? 'SSE'}</span>
          </div>
          <div className="table-counts">
            {(status?.core_completeness.tables ?? []).map((table) => (
              <div className="count-row vertical" key={table.api_name}>
                <div>
                  <span>{table.api_name}</span>
                  <small>
                    {table.present_trade_days}/{table.expected_trade_days}，最新 {table.latest_present_date ?? '-'}
                  </small>
                </div>
                <strong>{table.missing_trade_days.toLocaleString('zh-CN')}</strong>
              </div>
            ))}
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
    </>
  );
}

function BackfillConsole(props: { job: BackfillJob }) {
  const job = props.job;
  const successRatio =
    job.total_batches > 0 ? Math.round((job.succeeded_batches / job.total_batches) * 100) : 0;
  const latestBatch = job.latest_batch;
  const highlightedApis = job.api_progress.slice(0, 8);

  return (
    <section className="panel backfill-console" aria-label="回填任务控制台">
      <div className="panel-heading">
        <h2>回填任务控制台</h2>
        <StatusBadge status={job.status} />
      </div>

      <div className="backfill-hero">
        <div>
          <span>当前接口</span>
          <strong>{job.current_api_name ?? '-'}</strong>
          <small>游标 {job.latest_cursor_value ?? '-'}</small>
        </div>
        <div>
          <span>批次进度</span>
          <strong>
            {job.succeeded_batches.toLocaleString('zh-CN')}/{job.total_batches.toLocaleString('zh-CN')}
          </strong>
          <small>成功率 {successRatio}%</small>
        </div>
        <div>
          <span>失败/阻塞</span>
          <strong>
            {job.failed_batches.toLocaleString('zh-CN')}/{job.blocked_batches.toLocaleString('zh-CN')}
          </strong>
          <small>{job.error_message ?? '暂无最终错误'}</small>
        </div>
        <div>
          <span>吞吐与预计</span>
          <strong>{formatSpeed(job.batches_per_hour)}</strong>
          <small>{formatEta(job)}</small>
        </div>
      </div>

      {latestBatch ? (
        <div className="backfill-current">
          <div>
            <span>最近批次</span>
            <strong>#{latestBatch.batch_index}</strong>
          </div>
          <div>
            <span>接口</span>
            <strong>{latestBatch.api_name ?? '-'}</strong>
          </div>
          <div>
            <span>窗口</span>
            <strong>{formatWindow(latestBatch.start_date, latestBatch.end_date)}</strong>
          </div>
          <div>
            <span>写入</span>
            <strong>{latestBatch.rows_upserted.toLocaleString('zh-CN')}</strong>
          </div>
        </div>
      ) : null}

      <div className="backfill-api-grid">
        {highlightedApis.map((api) => (
          <article className="backfill-api-card" data-status={api.status} key={api.api_name}>
            <div>
              <strong>{api.api_name}</strong>
              <StatusBadge status={api.status} />
            </div>
            <dl>
              <div>
                <dt>成功</dt>
                <dd>{api.succeeded_batches.toLocaleString('zh-CN')}</dd>
              </div>
              <div>
                <dt>失败</dt>
                <dd>{api.failed_batches.toLocaleString('zh-CN')}</dd>
              </div>
              <div>
                <dt>游标</dt>
                <dd>{api.latest_cursor_value ?? '-'}</dd>
              </div>
              <div>
                <dt>写入</dt>
                <dd>{api.rows_upserted.toLocaleString('zh-CN')}</dd>
              </div>
            </dl>
            {api.latest_error_message ? <p>{api.latest_error_message}</p> : null}
            {api.suggestion ? <small>{api.suggestion}</small> : null}
          </article>
        ))}
      </div>
    </section>
  );
}

function formatTime(value: string | null) {
  if (!value) {
    return '-';
  }
  return new Intl.DateTimeFormat('zh-CN', {
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    month: '2-digit',
  }).format(new Date(value));
}

function formatSpeed(value: number | null) {
  if (value === null) {
    return '-';
  }
  return `${Math.round(value).toLocaleString('zh-CN')} 批/小时`;
}

function formatEta(job: BackfillJob) {
  if (!job.estimated_remaining_batches || !job.batches_per_hour) {
    return '预计剩余 -';
  }
  const seconds = Math.round((job.estimated_remaining_batches / job.batches_per_hour) * 3600);
  return `预计剩余 ${formatDuration(seconds)}`;
}

function formatDuration(seconds: number) {
  if (seconds < 3600) {
    const minutes = Math.max(1, Math.round(seconds / 60));
    return `${String(minutes)} 分钟`;
  }
  const hours = Math.round(seconds / 3600);
  if (hours < 48) {
    return `${String(hours)} 小时`;
  }
  const days = Math.round(hours / 24);
  return `${String(days)} 天`;
}

function formatWindow(startDate: string | null, endDate: string | null) {
  if (!startDate && !endDate) {
    return '-';
  }
  if (startDate === endDate || !startDate) {
    return endDate ?? '-';
  }
  if (!endDate) {
    return startDate;
  }
  return `${startDate} 至 ${endDate}`;
}
