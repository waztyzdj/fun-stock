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
}
