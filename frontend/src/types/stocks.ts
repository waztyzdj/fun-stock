export interface StockListItem {
  ts_code: string;
  symbol: string;
  name: string;
  area: string | null;
  industry: string | null;
  market: string | null;
  exchange: string | null;
  list_status: string | null;
  list_date: string | null;
}

export interface StockQuotePoint {
  trade_date: string;
  open: string | null;
  high: string | null;
  low: string | null;
  close: string | null;
  pct_chg: string | null;
  vol: string | null;
  amount: string | null;
}

export interface StockDetail {
  stock: StockListItem;
  quotes: StockQuotePoint[];
  factors: StockFactorSnapshot[];
  factor_history: StockFactorHistoryPoint[];
}

export interface StockFactorSnapshot {
  factor_code: string;
  value: string;
  factor_date: string;
  report_end_date: string | null;
}

export interface StockFactorHistoryPoint {
  factor_code: string;
  value: string;
  factor_date: string;
  report_end_date: string | null;
}
