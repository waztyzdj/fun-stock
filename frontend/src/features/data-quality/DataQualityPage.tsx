import { useCallback, useEffect, useState } from 'react';

import { fetchCoreCompleteness, fixBackfillBatches, repairCoreData } from '../../services/apiClient';
import type { BackfillBatchFixResult, CoreCompleteness, DataRepairResult } from '../../types/sync';

const today = new Date().toISOString().slice(0, 10);
const defaultStartDate = new Date(Date.now() - 120 * 24 * 60 * 60 * 1000).toISOString().slice(0, 10);
type QualityStep = 'scope' | 'scan' | 'repair' | 'batch';

export function DataQualityPage() {
  const [startDate, setStartDate] = useState(defaultStartDate);
  const [endDate, setEndDate] = useState(today);
  const [layer, setLayer] = useState<'app' | 'raw'>('app');
  const [activeStep, setActiveStep] = useState<QualityStep>('scope');
  const [report, setReport] = useState<CoreCompleteness | null>(null);
  const [repairResult, setRepairResult] = useState<DataRepairResult | null>(null);
  const [batchFixResult, setBatchFixResult] = useState<BackfillBatchFixResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const scan = useCallback(async (signal?: AbortSignal) => {
    setLoading(true);
    setError(null);
    try {
      const nextReport = await fetchCoreCompleteness({ startDate, endDate, layer, signal });
      setReport(nextReport);
      setActiveStep('scan');
    } catch (scanError) {
      if (scanError instanceof DOMException && scanError.name === 'AbortError') {
        return;
      }
      setError(scanError instanceof Error ? scanError.message : 'Unknown error');
    } finally {
      setLoading(false);
    }
  }, [endDate, layer, startDate]);

  async function repair(dryRun: boolean) {
    setLoading(true);
    setError(null);
    try {
      const result = await repairCoreData({ startDate, endDate, dryRun });
      setRepairResult(result);
      setActiveStep('repair');
      if (!dryRun) {
        setReport(await fetchCoreCompleteness({ startDate, endDate, layer }));
      }
    } catch (repairError) {
      setError(repairError instanceof Error ? repairError.message : 'Unknown error');
    } finally {
      setLoading(false);
    }
  }

  async function fixBatches(dryRun: boolean) {
    setLoading(true);
    setError(null);
    try {
      setBatchFixResult(await fixBackfillBatches({ startDate, endDate, dryRun }));
      setActiveStep('batch');
    } catch (fixError) {
      setError(fixError instanceof Error ? fixError.message : 'Unknown error');
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    const controller = new AbortController();
    void scan(controller.signal);
    return () => {
      controller.abort();
    };
  }, [scan]);

  return (
    <section className="workspace-panel">
      <header className="module-header">
        <div>
          <p className="eyebrow">Quality</p>
          <h1>数据质量</h1>
        </div>
        <button className="primary-button" type="button" disabled={loading} onClick={() => void scan()}>
          {loading ? '检查中' : '检查'}
        </button>
      </header>

      {error ? <p className="error-banner">数据质量接口读取失败：{error}</p> : null}

      <section className="quality-workflow">
        <ol className="quality-steps" aria-label="数据质量操作步骤">
          <QualityStepItem
            step="scope"
            activeStep={activeStep}
            title="选择范围"
            meta={`${startDate} 至 ${endDate}`}
            onSelect={setActiveStep}
          />
          <QualityStepItem
            step="scan"
            activeStep={activeStep}
            title="查看巡检"
            meta={report ? `${report.total_missing_trade_days.toLocaleString('zh-CN')} 个缺口` : '待检查'}
            onSelect={setActiveStep}
          />
          <QualityStepItem
            step="repair"
            activeStep={activeStep}
            title="归一化修复"
            meta={repairResult ? (repairResult.executed ? '已执行' : '已预览') : '待处理'}
            onSelect={setActiveStep}
          />
          <QualityStepItem
            step="batch"
            activeStep={activeStep}
            title="批次修正"
            meta={batchFixResult ? `${batchFixResult.fixed_batches.toLocaleString('zh-CN')} 可修正` : '可选'}
            onSelect={setActiveStep}
          />
        </ol>

        <div className="panel quality-action-panel">
          {activeStep === 'scope' ? (
            <ScopeStep
              endDate={endDate}
              layer={layer}
              loading={loading}
              startDate={startDate}
              onEndDateChange={setEndDate}
              onLayerChange={setLayer}
              onScan={() => void scan()}
              onStartDateChange={setStartDate}
            />
          ) : null}
          {activeStep === 'scan' ? (
            <ScanStep
              layer={layer}
              loading={loading}
              report={report}
              onRepairStep={() => {
                setActiveStep('repair');
              }}
              onRescan={() => void scan()}
            />
          ) : null}
          {activeStep === 'repair' ? (
            <RepairStep
              layer={layer}
              loading={loading}
              repairResult={repairResult}
              report={report}
              onDryRun={() => void repair(true)}
              onExecute={() => void repair(false)}
            />
          ) : null}
          {activeStep === 'batch' ? (
            <BatchStep
              batchFixResult={batchFixResult}
              loading={loading}
              onDryRun={() => void fixBatches(true)}
              onExecute={() => void fixBatches(false)}
            />
          ) : null}
        </div>
      </section>

      <section className="content-grid">
        <div className="panel wide">
          <div className="panel-heading">
            <h2>完整性巡检</h2>
            <span>
              {report?.layer === 'raw' ? '原始层' : '应用层'}缺口 {report?.total_missing_trade_days ?? 0}
            </span>
          </div>
          <div className="quality-table-list">
            {(report?.tables ?? []).map((table) => (
              <article className="quality-row" key={table.api_name}>
                <div>
                  <strong>{table.api_name}</strong>
                  <span>
                    {table.present_trade_days}/{table.expected_trade_days}，最新{' '}
                    {table.latest_present_date ?? '-'}
                  </span>
                </div>
                <div>
                  <strong>{table.missing_trade_days.toLocaleString('zh-CN')}</strong>
                  <span>缺失交易日</span>
                </div>
                <p>
                  缺口样例：
                  {table.missing_dates.length > 0 ? table.missing_dates.slice(0, 8).join('、') : '无'}
                </p>
              </article>
            ))}
          </div>
        </div>

        <div className="panel">
          <div className="panel-heading">
            <h2>修复建议</h2>
            <span>{repairResult?.executed ? '已执行' : '预览'}</span>
          </div>
          <div className="event-list">
            {(repairResult?.repair_ranges ?? []).map((range) => (
              <article className="event-item" key={`${range.start_date}-${range.end_date}`}>
                <div>
                  <strong>
                    {range.start_date} 至 {range.end_date}
                  </strong>
                  <span>{range.days} 日</span>
                </div>
              </article>
            ))}
            {repairResult ? (
              <p className="empty-text">
                写入：日行情 {repairResult.daily_quotes.toLocaleString('zh-CN')}，指数日线{' '}
                {repairResult.index_daily_quotes.toLocaleString('zh-CN')}，每日指标{' '}
                {repairResult.daily_indicators.toLocaleString('zh-CN')}，复权因子{' '}
                {repairResult.adj_factors.toLocaleString('zh-CN')}
              </p>
            ) : (
              <p className="empty-text">先预览修复计划，再执行归一化修复。</p>
            )}
          </div>
        </div>

        <div className="panel">
          <div className="panel-heading">
            <h2>批次修正</h2>
            <span>{batchFixResult ? '已扫描' : '待扫描'}</span>
          </div>
          <div className="event-list">
            <div className="button-row">
              <button className="secondary-button" type="button" onClick={() => void fixBatches(true)}>
                预览批次修正
              </button>
              <button className="primary-button" type="button" onClick={() => void fixBatches(false)}>
                执行批次修正
              </button>
            </div>
            {batchFixResult ? (
              <p className="empty-text">
                扫描 {batchFixResult.scanned_batches.toLocaleString('zh-CN')} 个批次，可修正{' '}
                {batchFixResult.fixed_batches.toLocaleString('zh-CN')} 个，仍失败{' '}
                {batchFixResult.still_failed_batches.toLocaleString('zh-CN')} 个，超时运行中{' '}
                {batchFixResult.stale_running_batches.toLocaleString('zh-CN')} 个。
              </p>
            ) : (
              <p className="empty-text">用于处理 failed 或长时间 running 但数据已归一化完成的批次。</p>
            )}
          </div>
        </div>
      </section>
    </section>
  );
}

interface QualityStepItemProps {
  step: QualityStep;
  activeStep: QualityStep;
  title: string;
  meta: string;
  onSelect: (step: QualityStep) => void;
}

function QualityStepItem({ step, activeStep, title, meta, onSelect }: QualityStepItemProps) {
  return (
    <li>
      <button
        className="quality-step-button"
        data-active={step === activeStep}
        type="button"
        onClick={() => {
          onSelect(step);
        }}
      >
        <strong>{title}</strong>
        <span>{meta}</span>
      </button>
    </li>
  );
}

interface ScopeStepProps {
  startDate: string;
  endDate: string;
  layer: 'app' | 'raw';
  loading: boolean;
  onStartDateChange: (value: string) => void;
  onEndDateChange: (value: string) => void;
  onLayerChange: (value: 'app' | 'raw') => void;
  onScan: () => void;
}

function ScopeStep({
  startDate,
  endDate,
  layer,
  loading,
  onEndDateChange,
  onLayerChange,
  onScan,
  onStartDateChange,
}: ScopeStepProps) {
  return (
    <>
      <div className="quality-action-heading">
        <span>第 1 步</span>
        <h2>选择巡检范围</h2>
      </div>
      <div className="guided-form">
        <label>
          <span>开始日期</span>
          <input
            type="date"
            value={startDate}
            onChange={(event) => {
              onStartDateChange(event.target.value);
            }}
          />
        </label>
        <label>
          <span>结束日期</span>
          <input
            type="date"
            value={endDate}
            onChange={(event) => {
              onEndDateChange(event.target.value);
            }}
          />
        </label>
        <label>
          <span>巡检层</span>
          <select
            value={layer}
            onChange={(event) => {
              onLayerChange(event.target.value === 'raw' ? 'raw' : 'app');
            }}
          >
            <option value="app">应用层 app</option>
            <option value="raw">原始层 raw</option>
          </select>
        </label>
      </div>
      <div className="guided-actions">
        <button className="primary-button" type="button" disabled={loading} onClick={onScan}>
          {loading ? '检查中' : '开始巡检'}
        </button>
      </div>
    </>
  );
}

interface ScanStepProps {
  report: CoreCompleteness | null;
  layer: 'app' | 'raw';
  loading: boolean;
  onRescan: () => void;
  onRepairStep: () => void;
}

function ScanStep({ report, layer, loading, onRepairStep, onRescan }: ScanStepProps) {
  const missing = report?.total_missing_trade_days ?? 0;
  return (
    <>
      <div className="quality-action-heading">
        <span>第 2 步</span>
        <h2>查看巡检结果</h2>
      </div>
      <div className="quality-result-hero" data-state={missing > 0 ? 'warning' : 'success'}>
        <strong>{report ? missing.toLocaleString('zh-CN') : '-'}</strong>
        <span>{report ? `${report.layer === 'raw' ? '原始层' : '应用层'}缺失交易日` : '尚未巡检'}</span>
      </div>
      <div className="quality-next-action">
        {report ? nextActionText(report, layer) : '先完成范围巡检。'}
      </div>
      <div className="guided-actions">
        <button className="secondary-button" type="button" disabled={loading} onClick={onRescan}>
          重新巡检
        </button>
        <button className="primary-button" type="button" disabled={!report} onClick={onRepairStep}>
          进入处理
        </button>
      </div>
    </>
  );
}

interface RepairStepProps {
  report: CoreCompleteness | null;
  repairResult: DataRepairResult | null;
  layer: 'app' | 'raw';
  loading: boolean;
  onDryRun: () => void;
  onExecute: () => void;
}

function RepairStep({ report, repairResult, layer, loading, onDryRun, onExecute }: RepairStepProps) {
  const hasAppGap = layer === 'app' && (report?.total_missing_trade_days ?? 0) > 0;
  return (
    <>
      <div className="quality-action-heading">
        <span>第 3 步</span>
        <h2>归一化修复</h2>
      </div>
      <div className="quality-next-action">{repairStepText(report, layer)}</div>
      <div className="guided-actions">
        <button className="secondary-button" type="button" disabled={loading || !hasAppGap} onClick={onDryRun}>
          预览修复
        </button>
        <button className="primary-button" type="button" disabled={loading || !hasAppGap} onClick={onExecute}>
          执行修复
        </button>
      </div>
      {repairResult ? (
        <div className="quality-action-summary">
          写入：日行情 {repairResult.daily_quotes.toLocaleString('zh-CN')}，指数日线{' '}
          {repairResult.index_daily_quotes.toLocaleString('zh-CN')}，每日指标{' '}
          {repairResult.daily_indicators.toLocaleString('zh-CN')}，复权因子{' '}
          {repairResult.adj_factors.toLocaleString('zh-CN')}。
        </div>
      ) : null}
    </>
  );
}

interface BatchStepProps {
  batchFixResult: BackfillBatchFixResult | null;
  loading: boolean;
  onDryRun: () => void;
  onExecute: () => void;
}

function BatchStep({ batchFixResult, loading, onDryRun, onExecute }: BatchStepProps) {
  return (
    <>
      <div className="quality-action-heading">
        <span>第 4 步</span>
        <h2>回填批次修正</h2>
      </div>
      <div className="quality-next-action">
        修正 failed 或长时间 running，但对应应用层数据已经完整的回填批次。
      </div>
      <div className="guided-actions">
        <button className="secondary-button" type="button" disabled={loading} onClick={onDryRun}>
          预览批次修正
        </button>
        <button className="primary-button" type="button" disabled={loading} onClick={onExecute}>
          执行批次修正
        </button>
      </div>
      {batchFixResult ? (
        <div className="quality-action-summary">
          扫描 {batchFixResult.scanned_batches.toLocaleString('zh-CN')} 个批次，可修正{' '}
          {batchFixResult.fixed_batches.toLocaleString('zh-CN')} 个，仍失败{' '}
          {batchFixResult.still_failed_batches.toLocaleString('zh-CN')} 个。
        </div>
      ) : null}
    </>
  );
}

function nextActionText(report: CoreCompleteness, layer: 'app' | 'raw'): string {
  if (report.total_missing_trade_days === 0) {
    return '当前范围没有缺口，可以进入批次修正或继续扩大日期范围。';
  }
  if (layer === 'raw') {
    return '原始层缺口需要先补拉 Tushare 数据，再回到应用层巡检。';
  }
  return '应用层存在缺口，下一步先预览归一化修复。';
}

function repairStepText(report: CoreCompleteness | null, layer: 'app' | 'raw'): string {
  if (!report) {
    return '先完成巡检，再根据缺口决定是否修复。';
  }
  if (layer === 'raw') {
    return '当前查看的是原始层，归一化修复只处理应用层缺口。';
  }
  if (report.total_missing_trade_days === 0) {
    return '应用层没有缺口，无需执行归一化修复。';
  }
  return '先预览修复计划，确认范围后再执行写入。';
}
