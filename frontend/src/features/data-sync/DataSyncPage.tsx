import { useEffect, useMemo, useState } from 'react';

import { Metric } from '../../components/Metric';
import { StatusBadge } from '../../components/StatusBadge';
import { fetchTushareSyncStatus } from '../../services/apiClient';
import type { SyncStatus } from '../../types/sync';

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

      <section className="content-grid">
        <div className="panel wide">
          <div className="panel-heading">
            <h2>回填任务</h2>
            <span>{status?.backfill_jobs.length ?? 0} 个任务</span>
          </div>
          <div className="event-list backfill-list">
            {(status?.backfill_jobs ?? []).map((job) => (
              <article className="event-item" key={job.id}>
                <div>
                  <strong>{job.name}</strong>
                  <StatusBadge status={job.status} />
                </div>
                <div className="backfill-summary-grid">
                  <SummaryItem label="当前游标" value={job.cursor_date ?? '-'} />
                  <SummaryItem
                    label="批次进度"
                    value={`${String(job.succeeded_batches)}/${String(job.total_batches)}`}
                  />
                  <SummaryItem label="失败批次" value={String(job.failed_batches)} />
                  <SummaryItem label="剩余交易日" value={formatNullableNumber(job.remaining_trade_days)} />
                  <SummaryItem label="预计剩余批次" value={formatNullableNumber(job.estimated_remaining_batches)} />
                  <SummaryItem label="写入行数" value={job.rows_upserted.toLocaleString('zh-CN')} />
                </div>
                {job.latest_batch ? (
                  <p>
                    当前批次 #{job.latest_batch.batch_index}：{job.latest_batch.start_date ?? '-'} 至{' '}
                    {job.latest_batch.end_date ?? '-'}
                  </p>
                ) : null}
                {job.error_message ? <p className="error-text">{job.error_message}</p> : null}
                <div className="batch-strip">
                  {job.recent_batches.map((batch) => (
                    <span className="batch-pill" data-status={batch.status} key={batch.batch_index}>
                      #{batch.batch_index} {batch.start_date ?? '-'} 至 {batch.end_date ?? '-'}
                    </span>
                  ))}
                </div>
              </article>
            ))}
            {status?.backfill_jobs.length === 0 ? <p className="empty-text">暂无回填任务记录</p> : null}
          </div>
        </div>

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
                    {table.present_trade_days}/{table.expected_trade_days}，最新{' '}
                    {table.latest_present_date ?? '-'}
                  </small>
                </div>
                <strong>{table.missing_trade_days.toLocaleString('zh-CN')}</strong>
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
    </>
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

function SummaryItem(props: { label: string; value: string }) {
  return (
    <div className="summary-item">
      <span>{props.label}</span>
      <strong>{props.value}</strong>
    </div>
  );
}

function formatNullableNumber(value: number | null) {
  return value === null ? '-' : value.toLocaleString('zh-CN');
}
