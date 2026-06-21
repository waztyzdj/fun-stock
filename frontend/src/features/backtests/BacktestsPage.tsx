import { useEffect, useState } from 'react';

import {
  fetchBacktestRun,
  fetchBacktestRuns,
  fetchStrategies,
  fetchStrategyDetail,
  runLongTermBacktest,
} from '../../services/apiClient';
import type {
  BacktestBenchmarkKind,
  BacktestPeriod,
  BacktestRunListItem,
  LongTermBacktestResult,
  StrategyDetail,
  StrategyFilter,
  StrategyListItem,
  StrategySort,
  StrategyUniverse,
} from '../../types/strategies';

const defaultFilters: StrategyFilter[] = [
  { factor_code: 'roe', operator: '>=', value: '12' },
  { factor_code: 'ocf_to_profit', operator: '>=', value: '80' },
  { factor_code: 'debt_to_assets', operator: '<=', value: '60' },
];

const defaultSort: StrategySort[] = [
  { factor_code: 'roe', direction: 'desc' },
  { factor_code: 'ocf_to_profit', direction: 'desc' },
];

const defaultUniverse: StrategyUniverse = {
  exclude_st: true,
  min_list_years: 3,
};

interface BenchmarkOption {
  kind: BacktestBenchmarkKind;
  label: string;
  name: string;
  tsCode: string;
  value: string;
}

const benchmarkOptions: BenchmarkOption[] = [
  {
    kind: 'index',
    label: '沪深300',
    name: '沪深300',
    tsCode: '000300.SH',
    value: 'index:000300.SH',
  },
  {
    kind: 'index',
    label: '中证500',
    name: '中证500',
    tsCode: '000905.SH',
    value: 'index:000905.SH',
  },
  {
    kind: 'index',
    label: '中证1000',
    name: '中证1000',
    tsCode: '000852.SH',
    value: 'index:000852.SH',
  },
  {
    kind: 'index',
    label: '中证全指',
    name: '中证全指',
    tsCode: '000985.CSI',
    value: 'index:000985.CSI',
  },
  {
    kind: 'same_universe',
    label: '同股票池等权',
    name: 'same universe equal weight',
    tsCode: '',
    value: 'same_universe',
  },
];

export function BacktestsPage() {
  const [startDate, setStartDate] = useState('2020-01-01');
  const [endDate, setEndDate] = useState(new Date().toISOString().slice(0, 10));
  const [frequency, setFrequency] = useState<'annual' | 'quarterly'>('annual');
  const [limit, setLimit] = useState(30);
  const [runName, setRunName] = useState('长线基本面质量回测');
  const [strategies, setStrategies] = useState<StrategyListItem[]>([]);
  const [selectedStrategyId, setSelectedStrategyId] = useState('');
  const [selectedStrategy, setSelectedStrategy] = useState<StrategyDetail | null>(null);
  const [strategyLoading, setStrategyLoading] = useState(false);
  const [commissionRate, setCommissionRate] = useState('0.0003');
  const [slippageRate, setSlippageRate] = useState('0');
  const [stampTaxRate, setStampTaxRate] = useState('0.001');
  const [useAdjustedPrices, setUseAdjustedPrices] = useState(true);
  const [selectedBenchmarkValue, setSelectedBenchmarkValue] = useState('index:000300.SH');
  const [runs, setRuns] = useState<BacktestRunListItem[]>([]);
  const [result, setResult] = useState<LongTermBacktestResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [historyLoading, setHistoryLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    void loadRunHistory(controller.signal);
    void loadStrategies(controller.signal);
    return () => {
      controller.abort();
    };
  }, []);

  useEffect(() => {
    if (!selectedStrategyId) {
      setSelectedStrategy(null);
      return undefined;
    }
    const controller = new AbortController();
    setStrategyLoading(true);
    fetchStrategyDetail(Number(selectedStrategyId), controller.signal)
      .then((strategy) => {
        setSelectedStrategy(strategy);
      })
      .catch((strategyError: unknown) => {
        if (strategyError instanceof DOMException && strategyError.name === 'AbortError') {
          return;
        }
        setError(strategyError instanceof Error ? strategyError.message : 'Unknown error');
      })
      .finally(() => {
        setStrategyLoading(false);
      });
    return () => {
      controller.abort();
    };
  }, [selectedStrategyId]);

  async function loadRunHistory(signal?: AbortSignal) {
    setHistoryLoading(true);
    try {
      setRuns(await fetchBacktestRuns(signal));
    } catch (historyError) {
      if (historyError instanceof DOMException && historyError.name === 'AbortError') {
        return;
      }
      setError(historyError instanceof Error ? historyError.message : 'Unknown error');
    } finally {
      setHistoryLoading(false);
    }
  }

  async function loadStrategies(signal?: AbortSignal) {
    try {
      setStrategies(await fetchStrategies(signal));
    } catch (strategyError) {
      if (strategyError instanceof DOMException && strategyError.name === 'AbortError') {
        return;
      }
      setError(strategyError instanceof Error ? strategyError.message : 'Unknown error');
    }
  }

  async function handleRunBacktest() {
    setLoading(true);
    setError(null);
    const activeFilters = selectedStrategy ? filtersFromStrategy(selectedStrategy) : defaultFilters;
    const activeSort = selectedStrategy ? sortFromStrategy(selectedStrategy) : defaultSort;
    const activeUniverse = selectedStrategy ? universeFromStrategy(selectedStrategy) : defaultUniverse;
    const selectedBenchmark = benchmarkFromValue(selectedBenchmarkValue);
    try {
      const nextResult = await runLongTermBacktest({
        as_of_date: null,
        end_date: endDate,
        filters: activeFilters,
        frequency,
        initial_cash: '1000000',
        limit,
        name: runName,
        sort: activeSort,
        start_date: startDate,
        strategy_id: selectedStrategy ? selectedStrategy.id : parseOptionalNumber(selectedStrategyId),
        universe: activeUniverse,
        commission_rate: normalizeRateInput(commissionRate),
        slippage_rate: normalizeRateInput(slippageRate),
        stamp_tax_rate: normalizeRateInput(stampTaxRate),
        use_adjusted_prices: useAdjustedPrices,
        benchmark_kind: selectedBenchmark.kind,
        benchmark_ts_code: selectedBenchmark.tsCode,
        benchmark_name: selectedBenchmark.name,
      });
      setResult(nextResult);
      await loadRunHistory();
    } catch (backtestError) {
      setError(backtestError instanceof Error ? backtestError.message : 'Unknown error');
    } finally {
      setLoading(false);
    }
  }

  async function handleOpenRun(runId: number) {
    setHistoryLoading(true);
    setError(null);
    try {
      setResult(await fetchBacktestRun(runId));
    } catch (runError) {
      setError(runError instanceof Error ? runError.message : 'Unknown error');
    } finally {
      setHistoryLoading(false);
    }
  }

  return (
    <section className="workspace-panel">
      <header className="module-header">
        <div>
          <p className="eyebrow">Backtests</p>
          <h1>回测中心</h1>
        </div>
      </header>

      {error ? <p className="error-banner">回测运行失败：{error}</p> : null}

      <section className="backtest-layout">
        <div className="panel">
          <div className="panel-heading">
            <h2>长线基本面回测</h2>
            <span>等权持有，按年度或季度调仓</span>
          </div>
          <div className="backtest-form">
            <label className="backtest-form-wide">
              <span>任务名称</span>
              <input
                value={runName}
                onChange={(event) => {
                  setRunName(event.target.value);
                }}
              />
            </label>
            <label className="backtest-form-wide">
              <span>回测策略</span>
              <select
                value={selectedStrategyId}
                onChange={(event) => {
                  setSelectedStrategyId(event.target.value);
                }}
              >
                <option value="">临时默认质量现金流策略</option>
                {strategies.map((strategy) => (
                  <option key={strategy.id} value={strategy.id}>
                    {strategy.name}
                  </option>
                ))}
              </select>
            </label>
            <label>
              <span>开始日期</span>
              <input
                type="date"
                value={startDate}
                onChange={(event) => {
                  setStartDate(event.target.value);
                }}
              />
            </label>
            <label>
              <span>结束日期</span>
              <input
                type="date"
                value={endDate}
                onChange={(event) => {
                  setEndDate(event.target.value);
                }}
              />
            </label>
            <label>
              <span>调仓频率</span>
              <select
                value={frequency}
                onChange={(event) => {
                  setFrequency(event.target.value === 'quarterly' ? 'quarterly' : 'annual');
                }}
              >
                <option value="annual">年度调仓</option>
                <option value="quarterly">季度调仓</option>
              </select>
            </label>
            <label>
              <span>持仓数量</span>
              <input
                max="100"
                min="1"
                type="number"
                value={limit}
                onChange={(event) => {
                  setLimit(clampNumber(event.target.value, 1, 100));
                }}
              />
            </label>
            <label>
              <span>基准指数</span>
              <select
                value={selectedBenchmarkValue}
                onChange={(event) => {
                  setSelectedBenchmarkValue(event.target.value);
                }}
              >
                {benchmarkOptions.map((option) => (
                  <option key={option.value} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </select>
            </label>
            <label>
              <span>佣金率</span>
              <input
                inputMode="decimal"
                value={commissionRate}
                onChange={(event) => {
                  setCommissionRate(event.target.value);
                }}
              />
            </label>
            <label>
              <span>滑点率</span>
              <input
                inputMode="decimal"
                value={slippageRate}
                onChange={(event) => {
                  setSlippageRate(event.target.value);
                }}
              />
            </label>
            <label>
              <span>印花税率</span>
              <input
                inputMode="decimal"
                value={stampTaxRate}
                onChange={(event) => {
                  setStampTaxRate(event.target.value);
                }}
              />
            </label>
          </div>
          <label className="checkbox-row">
            <input
              checked={useAdjustedPrices}
              type="checkbox"
              onChange={(event) => {
                setUseAdjustedPrices(event.target.checked);
              }}
            />
            <span>使用复权价格计算收益</span>
          </label>
          <div className="backtest-rule-box">
            <strong>{selectedStrategy ? selectedStrategy.name : '当前临时默认策略'}</strong>
            <span>{strategyLoading ? '策略读取中...' : strategyRuleSummary(selectedStrategy)}</span>
          </div>
          <button
            className="primary-button"
            disabled={loading || strategyLoading}
            type="button"
            onClick={() => {
              void handleRunBacktest();
            }}
          >
            {loading ? '回测中' : '运行回测'}
          </button>
        </div>

        <div className="panel">
          <div className="panel-heading">
            <h2>绩效摘要</h2>
            <span>{result ? `${result.start_date} 至 ${result.end_date}` : '等待运行'}</span>
          </div>
          <div className="backtest-summary-grid">
            <SummaryCard label="期末资产" value={formatMoney(result?.final_value)} />
            <SummaryCard label="基准资产" value={formatMoney(result?.benchmark_final_value)} />
            <SummaryCard label="策略来源" value={result?.strategy_name ?? '临时条件'} />
            <SummaryCard
              label="基准口径"
              value={result?.benchmark_name ?? benchmarkFromValue(selectedBenchmarkValue).label}
            />
            <SummaryCard label="价格口径" value={result?.use_adjusted_prices ? '复权' : '不复权'} />
            <SummaryCard label="累计收益" value={formatPercent(result?.total_return)} />
            <SummaryCard label="基准收益" value={formatPercent(result?.benchmark_return)} />
            <SummaryCard label="超额收益" value={formatPercent(result?.excess_return)} />
            <SummaryCard label="年化收益" value={formatPercent(result?.annualized_return)} />
            <SummaryCard label="最大回撤" value={formatPercent(result?.max_drawdown)} />
            <SummaryCard label="胜率" value={formatPercent(result?.win_rate)} />
            <SummaryCard label="平均换手" value={formatPercent(result?.average_turnover)} />
            <SummaryCard label="调仓次数" value={(result?.periods.length ?? 0).toLocaleString('zh-CN')} />
            <SummaryCard label="回测区间" value={formatRangeDays(result)} />
          </div>
          <div className="backtest-equity-line" aria-label="策略与基准净值对比">
            {(result?.periods ?? []).map((period) => (
              <span
                key={`strategy-${period.rebalance_date}`}
                style={{ height: `${String(equityHeight(result, period.portfolio_value))}%` }}
                title={`策略 ${period.rebalance_date}: ${formatMoney(period.portfolio_value)}`}
              />
            ))}
          </div>
          <div className="backtest-equity-line backtest-equity-line--benchmark" aria-label="基准净值对比">
            {(result?.periods ?? []).map((period) => (
              <span
                key={`benchmark-${period.rebalance_date}`}
                style={{ height: `${String(equityHeight(result, period.benchmark_value))}%` }}
                title={`基准 ${period.rebalance_date}: ${formatMoney(period.benchmark_value)}`}
              />
            ))}
          </div>
        </div>
      </section>

      <section className="panel backtest-period-panel">
        <div className="panel-heading">
          <h2>历史回测</h2>
          <span>{historyLoading ? '读取中' : `${runs.length.toLocaleString('zh-CN')} 条记录`}</span>
        </div>
        <div className="backtest-history-list">
          {runs.map((run) => (
            <button
              className="backtest-history-item"
              data-active={result?.id === run.id}
              key={run.id}
              type="button"
              onClick={() => void handleOpenRun(run.id)}
            >
              <strong>{run.name}</strong>
              <span>
                {run.start_date} 至 {run.end_date} / {run.frequency === 'quarterly' ? '季度' : '年度'}
              </span>
              <small>
                累计 {formatPercent(run.total_return)}，超额 {formatPercent(run.excess_return)}，创建于{' '}
                {formatDateTime(run.created_at)}
              </small>
            </button>
          ))}
          {runs.length === 0 ? <p className="empty-text">还没有保存过的回测任务。</p> : null}
        </div>
      </section>

      <BacktestComparisonPanel runs={runs} />

      <BacktestDiagnosticsPanel result={result} />

      <section className="panel backtest-period-panel">
        <div className="panel-heading">
          <h2>调仓明细</h2>
          <span>{(result?.periods.length ?? 0).toLocaleString('zh-CN')} 个区间</span>
        </div>
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>调仓日</th>
                <th>退出日</th>
                <th>入选数</th>
                <th>策略收益</th>
                <th>基准收益</th>
                <th>超额</th>
                <th>换手率</th>
                <th>主要持仓</th>
              </tr>
            </thead>
            <tbody>
              {(result?.periods ?? []).map((period) => (
                <tr key={period.rebalance_date}>
                  <td>{period.rebalance_date}</td>
                  <td>{period.exit_date}</td>
                  <td>{period.selected_count}</td>
                  <td>{formatPercent(period.period_return)}</td>
                  <td>{formatPercent(period.benchmark_return)}</td>
                  <td>{formatPercent(period.excess_return)}</td>
                  <td>{formatPercent(period.turnover_rate)}</td>
                  <td>
                    <div className="result-factor-list">
                      {period.holdings.slice(0, 5).map((holding) => (
                        <span key={`${period.rebalance_date}-${holding.ts_code}`}>
                          {holding.name} {formatPercent(holding.return_ratio)}
                        </span>
                      ))}
                    </div>
                  </td>
                </tr>
              ))}
              {result ? null : (
                <tr>
                  <td colSpan={8}>
                    <span className="empty-text">运行回测后展示年度或季度调仓结果。</span>
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </section>
    </section>
  );
}

function BacktestComparisonPanel({ runs }: { runs: BacktestRunListItem[] }) {
  const comparedRuns = runs.slice(0, 5);
  const bestRun = comparedRuns.reduce<BacktestRunListItem | null>((currentBest, run) => {
    if (!currentBest || Number(run.excess_return) > Number(currentBest.excess_return)) {
      return run;
    }
    return currentBest;
  }, null);

  return (
    <section className="panel backtest-period-panel">
      <div className="panel-heading">
        <h2>策略横向对比</h2>
        <span>{comparedRuns.length.toLocaleString('zh-CN')} 个最近回测</span>
      </div>
      {bestRun ? (
        <div className="backtest-compare-leader">
          <span>当前超额收益最高</span>
          <strong>{bestRun.name}</strong>
          <small>
            超额 {formatPercent(bestRun.excess_return)}，累计 {formatPercent(bestRun.total_return)}
          </small>
        </div>
      ) : null}
      <div className="backtest-compare-grid">
        {comparedRuns.map((run) => (
          <article className="backtest-compare-card" key={run.id}>
            <header>
              <strong>{run.name}</strong>
              <span>{run.frequency === 'quarterly' ? '季度调仓' : '年度调仓'}</span>
            </header>
            <div className="backtest-compare-bars">
              <span
                style={{ height: `${String(compareBarHeight(comparedRuns, run.total_return))}%` }}
                title={`累计收益 ${formatPercent(run.total_return)}`}
              />
              <span
                data-kind="benchmark"
                style={{ height: `${String(compareBarHeight(comparedRuns, run.benchmark_return))}%` }}
                title={`基准收益 ${formatPercent(run.benchmark_return)}`}
              />
              <span
                data-kind="excess"
                style={{ height: `${String(compareBarHeight(comparedRuns, run.excess_return))}%` }}
                title={`超额收益 ${formatPercent(run.excess_return)}`}
              />
            </div>
            <dl>
              <div>
                <dt>累计</dt>
                <dd>{formatPercent(run.total_return)}</dd>
              </div>
              <div>
                <dt>基准</dt>
                <dd>{formatPercent(run.benchmark_return)}</dd>
              </div>
              <div>
                <dt>超额</dt>
                <dd>{formatPercent(run.excess_return)}</dd>
              </div>
              <div>
                <dt>年化</dt>
                <dd>{formatPercent(run.annualized_return)}</dd>
              </div>
              <div>
                <dt>回撤</dt>
                <dd>{formatPercent(run.max_drawdown)}</dd>
              </div>
              <div>
                <dt>胜率</dt>
                <dd>{formatPercent(run.win_rate)}</dd>
              </div>
            </dl>
          </article>
        ))}
      </div>
      {comparedRuns.length === 0 ? <p className="empty-text">保存回测后会自动生成横向对比。</p> : null}
    </section>
  );
}

function BacktestDiagnosticsPanel({ result }: { result: LongTermBacktestResult | null }) {
  const breakdown = buildPeriodBreakdown(result?.periods ?? []);

  return (
    <section className="panel backtest-period-panel">
      <div className="panel-heading">
        <h2>风险诊断</h2>
        <span>{breakdown.length.toLocaleString('zh-CN')} 个年度桶</span>
      </div>
      <div className="backtest-diagnostics-grid">
        <SummaryCard label="最大回撤" value={formatPercent(result?.max_drawdown)} />
        <SummaryCard label="盈利区间占比" value={formatPercent(result?.win_rate)} />
        <SummaryCard label="平均换手率" value={formatPercent(result?.average_turnover)} />
      </div>
      <div className="backtest-breakdown-list">
        {breakdown.map((item) => (
          <article className="backtest-breakdown-row" key={item.year}>
            <strong>{item.year}</strong>
            <dl>
              <div>
                <dt>区间数</dt>
                <dd>{item.periodCount.toLocaleString('zh-CN')}</dd>
              </div>
              <div>
                <dt>策略收益</dt>
                <dd>{formatPercent(item.periodReturn)}</dd>
              </div>
              <div>
                <dt>基准收益</dt>
                <dd>{formatPercent(item.benchmarkReturn)}</dd>
              </div>
              <div>
                <dt>超额收益</dt>
                <dd>{formatPercent(item.excessReturn)}</dd>
              </div>
              <div>
                <dt>平均换手</dt>
                <dd>{formatPercent(item.averageTurnover)}</dd>
              </div>
            </dl>
          </article>
        ))}
        {result ? null : <p className="empty-text">运行或打开历史回测后展示年度拆解。</p>}
      </div>
    </section>
  );
}

function SummaryCard(props: { label: string; value: string }) {
  return (
    <div className="status-block">
      <span>{props.label}</span>
      <strong>{props.value}</strong>
    </div>
  );
}

function filtersFromStrategy(strategy: StrategyDetail): StrategyFilter[] {
  return (strategy.strategy_json.filters ?? []).map((filter) => ({
    factor_code: filter.factor,
    operator: filter.op,
    value: filter.value,
  }));
}

function sortFromStrategy(strategy: StrategyDetail): StrategySort[] {
  return (strategy.strategy_json.sort ?? []).map((sort) => ({
    factor_code: sort.factor,
    direction: sort.direction,
  }));
}

function universeFromStrategy(strategy: StrategyDetail): StrategyUniverse {
  return {
    exclude_st: strategy.strategy_json.universe?.exclude_st ?? defaultUniverse.exclude_st,
    min_list_years: strategy.strategy_json.universe?.min_list_years ?? defaultUniverse.min_list_years,
  };
}

function benchmarkFromValue(value: string): BenchmarkOption {
  return benchmarkOptions.find((option) => option.value === value) ?? benchmarkOptions[0];
}

function strategyRuleSummary(strategy: StrategyDetail | null): string {
  const filters = strategy ? filtersFromStrategy(strategy) : defaultFilters;
  const sort = strategy ? sortFromStrategy(strategy) : defaultSort;
  const filterText =
    filters.length > 0
      ? filters
          .map((filter) => `${filter.factor_code} ${filter.operator} ${filter.value}`)
          .join('，')
      : '无筛选条件';
  const sortText =
    sort.length > 0
      ? sort
          .map((item) => `${item.factor_code} ${item.direction === 'desc' ? '降序' : '升序'}`)
          .join('，')
      : '无排序规则';
  return `${filterText}；排序：${sortText}。`;
}

function normalizeRateInput(value: string): string {
  const parsed = Number(value);
  if (!Number.isFinite(parsed) || parsed < 0) {
    return '0';
  }
  return String(parsed);
}

function parseOptionalNumber(value: string): number | null {
  if (value.trim() === '') {
    return null;
  }
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : null;
}

function clampNumber(value: string, min: number, max: number): number {
  const parsed = Number(value);
  if (!Number.isFinite(parsed)) {
    return min;
  }
  return Math.min(max, Math.max(min, parsed));
}

function formatMoney(value: string | null | undefined): string {
  const parsed = Number(value);
  if (!Number.isFinite(parsed)) {
    return '-';
  }
  return parsed.toLocaleString('zh-CN', {
    maximumFractionDigits: 0,
    minimumFractionDigits: 0,
  });
}

function formatPercent(value: string | null | undefined): string {
  const parsed = Number(value);
  if (!Number.isFinite(parsed)) {
    return '-';
  }
  return `${(parsed * 100).toFixed(2)}%`;
}

function formatRangeDays(result: LongTermBacktestResult | null): string {
  if (!result) {
    return '-';
  }
  const days = (new Date(result.end_date).getTime() - new Date(result.start_date).getTime()) / 86400000;
  return `${Math.max(0, Math.round(days)).toLocaleString('zh-CN')} 天`;
}

function formatDateTime(value: string): string {
  return value.replace('T', ' ').slice(0, 19);
}

function buildPeriodBreakdown(periods: BacktestPeriod[]) {
  const buckets = new Map<
    string,
    {
      benchmarkMultiplier: number;
      periodCount: number;
      strategyMultiplier: number;
      turnoverTotal: number;
    }
  >();
  for (const period of periods) {
    const year = period.exit_date.slice(0, 4);
    const bucket = buckets.get(year) ?? {
      benchmarkMultiplier: 1,
      periodCount: 0,
      strategyMultiplier: 1,
      turnoverTotal: 0,
    };
    bucket.periodCount += 1;
    bucket.strategyMultiplier *= 1 + Number(period.period_return || 0);
    bucket.benchmarkMultiplier *= 1 + Number(period.benchmark_return || 0);
    bucket.turnoverTotal += Number(period.turnover_rate || 0);
    buckets.set(year, bucket);
  }
  return [...buckets.entries()]
    .map(([year, bucket]) => {
      const periodReturn = bucket.strategyMultiplier - 1;
      const benchmarkReturn = bucket.benchmarkMultiplier - 1;
      return {
        averageTurnover: String(bucket.turnoverTotal / Math.max(1, bucket.periodCount)),
        benchmarkReturn: String(benchmarkReturn),
        excessReturn: String(periodReturn - benchmarkReturn),
        periodCount: bucket.periodCount,
        periodReturn: String(periodReturn),
        year,
      };
    })
    .sort((first, second) => first.year.localeCompare(second.year));
}

function compareBarHeight(runs: BacktestRunListItem[], value: string): number {
  const values = runs
    .flatMap((run) => [Number(run.total_return), Number(run.benchmark_return), Number(run.excess_return)])
    .filter(Number.isFinite);
  const parsed = Number(value);
  const min = Math.min(...values, 0);
  const max = Math.max(...values, 0.01);
  const ratio = (parsed - min) / (max - min || 1);
  return Number.isFinite(ratio) ? Math.max(8, Math.round(ratio * 100)) : 8;
}

function equityHeight(result: LongTermBacktestResult | null, value: string): number {
  const values = (result?.periods ?? [])
    .flatMap((period) => [Number(period.portfolio_value), Number(period.benchmark_value)])
    .filter(Number.isFinite);
  const parsed = Number(value);
  const min = Math.min(...values);
  const max = Math.max(...values);
  const ratio = max === min ? 0.5 : (parsed - min) / (max - min);
  return Number.isFinite(ratio) ? Math.max(8, Math.round(ratio * 100)) : 8;
}
