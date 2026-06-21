export interface SyncJob {
  api_name: string;
  status: string;
  cursor_value: string | null;
  last_success_at: string | null;
  updated_at: string;
  error_message: string | null;
}

export interface ProblemRun {
  api_name: string;
  status: string;
  run_id: number;
  window_start: string | null;
  window_end: string | null;
  started_at: string;
  finished_at: string | null;
  error_message: string | null;
}

export interface QualityAlert {
  api_name: string;
  status: string;
  severity: string;
  check_name: string;
  message: string | null;
  observed_value: string | null;
  created_at: string;
}

export interface TableCount {
  name: string;
  rows: number;
}

export interface BackfillBatch {
  batch_index: number;
  api_name: string | null;
  status: string;
  cursor_date: string | null;
  cursor_value: string | null;
  start_date: string | null;
  end_date: string | null;
  trade_days: number;
  windows: number;
  rows_fetched: number;
  rows_upserted: number;
  started_at: string;
  finished_at: string | null;
  error_message: string | null;
}

export interface BackfillApiProgress {
  api_name: string;
  status: string;
  total_batches: number;
  succeeded_batches: number;
  failed_batches: number;
  blocked_batches: number;
  running_batches: number;
  rows_fetched: number;
  rows_upserted: number;
  latest_cursor_value: string | null;
  latest_started_at: string;
  latest_finished_at: string | null;
  latest_error_message: string | null;
  suggestion: string | null;
}

export interface BackfillJob {
  id: number;
  name: string;
  task_type: string;
  status: string;
  start_date: string | null;
  end_date: string | null;
  cursor_date: string | null;
  total_batches: number;
  succeeded_batches: number;
  failed_batches: number;
  blocked_batches: number;
  total_windows: number;
  rows_fetched: number;
  rows_upserted: number;
  started_at: string;
  finished_at: string | null;
  error_message: string | null;
  recent_batches: BackfillBatch[];
  is_running: boolean;
  remaining_trade_days: number | null;
  estimated_remaining_batches: number | null;
  latest_batch: BackfillBatch | null;
  current_api_name: string | null;
  latest_cursor_value: string | null;
  elapsed_seconds: number;
  batches_per_hour: number | null;
  api_progress: BackfillApiProgress[];
}

export interface MissingDateRange {
  start_date: string;
  end_date: string;
  days: number;
}

export interface TableCompleteness {
  api_name: string;
  table_name: string;
  expected_trade_days: number;
  present_trade_days: number;
  missing_trade_days: number;
  latest_present_date: string | null;
  completeness_ratio: number;
  missing_dates: string[];
  repair_ranges: MissingDateRange[];
}

export interface CoreCompleteness {
  layer: string;
  exchange: string;
  start_date: string;
  end_date: string;
  total_missing_trade_days: number;
  tables: TableCompleteness[];
}

export interface SyncStatus {
  jobs: SyncJob[];
  problem_runs: ProblemRun[];
  quality_alerts: QualityAlert[];
  table_counts: TableCount[];
  backfill_jobs: BackfillJob[];
  core_completeness: CoreCompleteness;
  retryable_failed_count: number;
  blocked_count: number;
}

export interface DataRepairResult {
  start_date: string;
  end_date: string;
  missing_trade_days: number;
  repair_ranges: MissingDateRange[];
  executed: boolean;
  daily_quotes: number;
  index_daily_quotes: number;
  daily_indicators: number;
  adj_factors: number;
}

export interface BackfillBatchFixResult {
  scanned_batches: number;
  fixed_batches: number;
  still_failed_batches: number;
  stale_running_batches: number;
}
