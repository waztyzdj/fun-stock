export interface FactorDefinition {
  code: string;
  name: string;
  category: string;
  unit: string | null;
  period_type: string;
  source: string;
  calculation_method: string;
  description: string;
  sort_direction: 'asc' | 'desc';
  value_count: number;
  stock_count: number;
  latest_factor_date: string | null;
  latest_report_end_date: string | null;
  latest_value_count: number;
}

export interface FactorBuildStatus {
  total_value_count: number;
  factor_count: number;
  stock_count: number;
  latest_factor_date: string | null;
  latest_report_end_date: string | null;
  latest_updated_at: string | null;
}

export interface FactorBuildResult {
  rows: number;
  start_date: string | null;
  status: FactorBuildStatus;
}

export type FactorQualityStatus = 'ready' | 'warning' | 'empty';

export interface FactorQualityItem {
  factor_code: string;
  factor_name: string;
  category: string;
  status: FactorQualityStatus;
  value_count: number;
  stock_count: number;
  latest_factor_date: string | null;
  latest_value_count: number;
  universe_stock_count: number;
  coverage_ratio: string;
  missing_stock_count: number;
  zero_value_count: number;
  negative_value_count: number;
}

export interface StrategyUniverse {
  exclude_st: boolean;
  min_list_years: number | null;
}

export type StrategyOperator = '>=' | '<=' | '>' | '<' | '=';

export interface StrategyFilter {
  factor_code: string;
  operator: StrategyOperator;
  value: string;
}

export interface StrategySort {
  factor_code: string;
  direction: 'asc' | 'desc';
}

export interface StrategyScreenRequest {
  universe: StrategyUniverse;
  filters: StrategyFilter[];
  sort: StrategySort[];
  as_of_date: string | null;
  limit: number;
}

export interface FactorValueSnapshot {
  factor_code: string;
  value: string;
  factor_date: string;
  report_end_date: string | null;
}

export interface StrategyFilterEvaluation {
  factor_code: string;
  operator: StrategyOperator;
  threshold: string;
  value: string | null;
  factor_date: string | null;
  passed: boolean;
  distance_ratio: string | null;
}

export interface StrategyScreenItem {
  ts_code: string;
  name: string;
  industry: string | null;
  market: string | null;
  list_date: string | null;
  factor_values: FactorValueSnapshot[];
  score: string;
  filter_evaluations: StrategyFilterEvaluation[];
}

export interface StrategyScreenResult {
  total: number;
  items: StrategyScreenItem[];
  near_misses: StrategyScreenItem[];
}

export interface StrategyListItem {
  id: number;
  name: string;
  description: string | null;
  status: string;
}

export interface SavedStrategyJson {
  universe?: Partial<StrategyUniverse>;
  filters?: {
    factor: string;
    op: StrategyOperator;
    value: string;
  }[];
  sort?: {
    factor: string;
    direction: 'asc' | 'desc';
  }[];
}

export interface StrategyDetail extends StrategyListItem {
  strategy_json: SavedStrategyJson;
}

export interface StrategySaveResult {
  id: number;
  name: string;
  status: string;
}

export interface BacktestHolding {
  ts_code: string;
  name: string;
  weight: string;
  entry_price: string | null;
  exit_price: string | null;
  return_ratio: string | null;
}

export interface BacktestPeriod {
  rebalance_date: string;
  exit_date: string;
  selected_count: number;
  period_return: string;
  benchmark_return: string;
  excess_return: string;
  turnover_rate: string;
  portfolio_value: string;
  benchmark_value: string;
  holdings: BacktestHolding[];
}

export type BacktestBenchmarkKind = 'index' | 'same_universe';

export interface LongTermBacktestRequest extends StrategyScreenRequest {
  name: string;
  strategy_id: number | null;
  start_date: string;
  end_date: string;
  frequency: 'annual' | 'quarterly';
  initial_cash: string;
  commission_rate: string;
  slippage_rate: string;
  stamp_tax_rate: string;
  use_adjusted_prices: boolean;
  benchmark_kind: BacktestBenchmarkKind;
  benchmark_ts_code: string;
  benchmark_name: string;
}

export interface LongTermBacktestResult {
  id: number | null;
  name: string | null;
  strategy_id: number | null;
  strategy_name: string | null;
  benchmark_kind: string;
  benchmark_ts_code: string | null;
  benchmark_name: string;
  start_date: string;
  end_date: string;
  frequency: string;
  initial_cash: string;
  commission_rate: string;
  slippage_rate: string;
  stamp_tax_rate: string;
  use_adjusted_prices: boolean;
  final_value: string;
  benchmark_final_value: string;
  total_return: string;
  benchmark_return: string;
  excess_return: string;
  annualized_return: string;
  max_drawdown: string;
  win_rate: string;
  average_turnover: string;
  periods: BacktestPeriod[];
}

export interface BacktestRunListItem {
  id: number;
  name: string;
  status: string;
  start_date: string;
  end_date: string;
  frequency: string;
  final_value: string;
  total_return: string;
  benchmark_return: string;
  excess_return: string;
  annualized_return: string;
  max_drawdown: string;
  win_rate: string;
  average_turnover: string;
  created_at: string;
}
