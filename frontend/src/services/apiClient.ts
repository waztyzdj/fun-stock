import type { StockDetail, StockListItem } from '../types/stocks';
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
