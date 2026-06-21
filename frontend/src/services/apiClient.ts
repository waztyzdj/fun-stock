import type { StockDetail, StockListItem } from '../types/stocks';
import type {
  BacktestRunListItem,
  LongTermBacktestRequest,
  LongTermBacktestResult,
  FactorBuildResult,
  FactorBuildStatus,
  FactorDefinition,
  FactorQualityItem,
  StrategyDetail,
  StrategyListItem,
  StrategySaveResult,
  StrategyScreenRequest,
  StrategyScreenResult,
} from '../types/strategies';
import type {
  BackfillBatchFixResult,
  CoreCompleteness,
  DataRepairResult,
  SyncStatus,
} from '../types/sync';

const apiBaseUrl = String(import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000/api/v1');

export async function fetchTushareSyncStatus(signal?: AbortSignal): Promise<SyncStatus> {
  const response = await fetch(`${apiBaseUrl}/sync/tushare/status`, { signal });
  if (!response.ok) {
    throw new Error(`HTTP ${String(response.status)}`);
  }
  return (await response.json()) as SyncStatus;
}

export async function fetchCoreCompleteness(params: {
  startDate: string;
  endDate: string;
  layer?: 'app' | 'raw';
  signal?: AbortSignal;
}): Promise<CoreCompleteness> {
  const searchParams = new URLSearchParams({
    start_date: params.startDate,
    end_date: params.endDate,
    layer: params.layer ?? 'app',
  });
  const response = await fetch(`${apiBaseUrl}/sync/tushare/completeness?${searchParams}`, {
    signal: params.signal,
  });
  if (!response.ok) {
    throw new Error(`HTTP ${String(response.status)}`);
  }
  return (await response.json()) as CoreCompleteness;
}

export async function repairCoreData(params: {
  startDate: string;
  endDate: string;
  dryRun: boolean;
}): Promise<DataRepairResult> {
  const searchParams = new URLSearchParams({
    start_date: params.startDate,
    end_date: params.endDate,
    dry_run: String(params.dryRun),
  });
  const response = await fetch(`${apiBaseUrl}/sync/tushare/repair?${searchParams}`, {
    method: 'POST',
  });
  if (!response.ok) {
    throw new Error(`HTTP ${String(response.status)}`);
  }
  return (await response.json()) as DataRepairResult;
}

export async function fixBackfillBatches(params: {
  startDate: string;
  endDate: string;
  dryRun: boolean;
}): Promise<BackfillBatchFixResult> {
  const searchParams = new URLSearchParams({
    start_date: params.startDate,
    end_date: params.endDate,
    dry_run: String(params.dryRun),
  });
  const response = await fetch(`${apiBaseUrl}/sync/tushare/backfill-batches/fix?${searchParams}`, {
    method: 'POST',
  });
  if (!response.ok) {
    throw new Error(`HTTP ${String(response.status)}`);
  }
  return (await response.json()) as BackfillBatchFixResult;
}

export async function fetchStocks(params: {
  query?: string;
  limit?: number;
  signal?: AbortSignal;
}): Promise<StockListItem[]> {
  const searchParams = new URLSearchParams({
    limit: String(params.limit ?? 50),
  });
  if (params.query) {
    searchParams.set('q', params.query);
  }
  const response = await fetch(`${apiBaseUrl}/stocks?${searchParams}`, {
    signal: params.signal,
  });
  if (!response.ok) {
    throw new Error(`HTTP ${String(response.status)}`);
  }
  return (await response.json()) as StockListItem[];
}

export async function fetchStockDetail(params: {
  tsCode: string;
  quoteLimit?: number;
  signal?: AbortSignal;
}): Promise<StockDetail> {
  const searchParams = new URLSearchParams({
    quote_limit: String(params.quoteLimit ?? 60),
  });
  const response = await fetch(`${apiBaseUrl}/stocks/${params.tsCode}?${searchParams}`, {
    signal: params.signal,
  });
  if (!response.ok) {
    throw new Error(`HTTP ${String(response.status)}`);
  }
  return (await response.json()) as StockDetail;
}

export async function fetchStrategyFactors(signal?: AbortSignal): Promise<FactorDefinition[]> {
  const response = await fetch(`${apiBaseUrl}/strategies/factors`, { signal });
  if (!response.ok) {
    throw new Error(`HTTP ${String(response.status)}`);
  }
  return (await response.json()) as FactorDefinition[];
}

export async function fetchFactorBuildStatus(signal?: AbortSignal): Promise<FactorBuildStatus> {
  const response = await fetch(`${apiBaseUrl}/strategies/factors/build-status`, { signal });
  if (!response.ok) {
    throw new Error(`HTTP ${String(response.status)}`);
  }
  return (await response.json()) as FactorBuildStatus;
}

export async function buildFactorValues(params: {
  startDate: string | null;
}): Promise<FactorBuildResult> {
  const response = await fetch(`${apiBaseUrl}/strategies/factors/build`, {
    body: JSON.stringify({ start_date: params.startDate }),
    headers: { 'Content-Type': 'application/json' },
    method: 'POST',
  });
  if (!response.ok) {
    throw new Error(`HTTP ${String(response.status)}`);
  }
  return (await response.json()) as FactorBuildResult;
}

export async function fetchFactorQuality(signal?: AbortSignal): Promise<FactorQualityItem[]> {
  const response = await fetch(`${apiBaseUrl}/strategies/factors/quality`, { signal });
  if (!response.ok) {
    throw new Error(`HTTP ${String(response.status)}`);
  }
  return (await response.json()) as FactorQualityItem[];
}

export async function fetchStrategies(signal?: AbortSignal): Promise<StrategyListItem[]> {
  const response = await fetch(`${apiBaseUrl}/strategies`, { signal });
  if (!response.ok) {
    throw new Error(`HTTP ${String(response.status)}`);
  }
  return (await response.json()) as StrategyListItem[];
}

export async function fetchStrategyDetail(
  strategyId: number,
  signal?: AbortSignal,
): Promise<StrategyDetail> {
  const response = await fetch(`${apiBaseUrl}/strategies/${String(strategyId)}`, { signal });
  if (!response.ok) {
    throw new Error(`HTTP ${String(response.status)}`);
  }
  return (await response.json()) as StrategyDetail;
}

export async function screenStrategy(
  request: StrategyScreenRequest,
  signal?: AbortSignal,
): Promise<StrategyScreenResult> {
  const response = await fetch(`${apiBaseUrl}/strategies/screen`, {
    body: JSON.stringify(request),
    headers: { 'Content-Type': 'application/json' },
    method: 'POST',
    signal,
  });
  if (!response.ok) {
    throw new Error(`HTTP ${String(response.status)}`);
  }
  return (await response.json()) as StrategyScreenResult;
}

export async function saveStrategy(params: {
  name: string;
  description?: string;
  request: StrategyScreenRequest;
}): Promise<StrategySaveResult> {
  const response = await fetch(`${apiBaseUrl}/strategies`, {
    body: JSON.stringify({
      ...params.request,
      description: params.description ?? null,
      name: params.name,
    }),
    headers: { 'Content-Type': 'application/json' },
    method: 'POST',
  });
  if (!response.ok) {
    throw new Error(`HTTP ${String(response.status)}`);
  }
  return (await response.json()) as StrategySaveResult;
}

export async function runLongTermBacktest(
  request: LongTermBacktestRequest,
  signal?: AbortSignal,
): Promise<LongTermBacktestResult> {
  const response = await fetch(`${apiBaseUrl}/backtests/long-term`, {
    body: JSON.stringify(request),
    headers: { 'Content-Type': 'application/json' },
    method: 'POST',
    signal,
  });
  if (!response.ok) {
    throw new Error(`HTTP ${String(response.status)}`);
  }
  return (await response.json()) as LongTermBacktestResult;
}

export async function fetchBacktestRuns(signal?: AbortSignal): Promise<BacktestRunListItem[]> {
  const response = await fetch(`${apiBaseUrl}/backtests`, { signal });
  if (!response.ok) {
    throw new Error(`HTTP ${String(response.status)}`);
  }
  return (await response.json()) as BacktestRunListItem[];
}

export async function fetchBacktestRun(
  runId: number,
  signal?: AbortSignal,
): Promise<LongTermBacktestResult> {
  const response = await fetch(`${apiBaseUrl}/backtests/${String(runId)}`, { signal });
  if (!response.ok) {
    throw new Error(`HTTP ${String(response.status)}`);
  }
  return (await response.json()) as LongTermBacktestResult;
}
