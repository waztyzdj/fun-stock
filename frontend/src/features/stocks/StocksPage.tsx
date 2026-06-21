import { useEffect, useMemo, useState } from 'react';

import { fetchStockDetail, fetchStocks } from '../../services/apiClient';
import type { StockDetail, StockListItem, StockQuotePoint } from '../../types/stocks';

export function StocksPage() {
  const [query, setQuery] = useState('');
  const [stocks, setStocks] = useState<StockListItem[]>([]);
  const [selectedTsCode, setSelectedTsCode] = useState<string | null>(null);
  const [detail, setDetail] = useState<StockDetail | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function loadStocks(signal?: AbortSignal) {
    setLoading(true);
    setError(null);
    try {
      const items = await fetchStocks({ query, limit: 50, signal });
      setStocks(items);
      if (!selectedTsCode && items.length > 0) {
        setSelectedTsCode(items[0].ts_code);
      }
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
    void loadStocks(controller.signal);
    return () => {
      controller.abort();
    };
  }, []);

  useEffect(() => {
    if (!selectedTsCode) {
      setDetail(null);
      return;
    }
    const controller = new AbortController();
    fetchStockDetail({ tsCode: selectedTsCode, quoteLimit: 60, signal: controller.signal })
      .then(setDetail)
      .catch((detailError: unknown) => {
        if (detailError instanceof DOMException && detailError.name === 'AbortError') {
          return;
        }
        setError(detailError instanceof Error ? detailError.message : 'Unknown error');
      });
    return () => {
      controller.abort();
    };
  }, [selectedTsCode]);

  const latestQuote = detail?.quotes.at(-1) ?? null;
  const chartPoints = useMemo(() => buildChartPoints(detail?.quotes ?? []), [detail]);

  return (
    <section className="workspace-panel">
      <header className="module-header">
        <div>
          <p className="eyebrow">Stocks</p>
          <h1>股票中心</h1>
        </div>
        <form
          className="search-box"
          onSubmit={(event) => {
            event.preventDefault();
            void loadStocks();
          }}
        >
          <input
            placeholder="代码、简称、名称"
            value={query}
            onChange={(event) => {
              setQuery(event.target.value);
            }}
          />
          <button className="primary-button" type="submit">
            {loading ? '搜索中' : '搜索'}
          </button>
        </form>
      </header>

      {error ? <p className="error-banner">股票数据读取失败：{error}</p> : null}

      <section className="stocks-layout">
        <div className="panel">
          <div className="panel-heading">
            <h2>股票列表</h2>
            <span>{stocks.length} 条</span>
          </div>
          <div className="stock-list">
            {stocks.map((stock) => (
              <button
                className="stock-row"
                data-active={selectedTsCode === stock.ts_code}
                key={stock.ts_code}
                onClick={() => {
                  setSelectedTsCode(stock.ts_code);
                }}
                type="button"
              >
                <strong>{stock.name}</strong>
                <span>{stock.ts_code}</span>
                <small>{stock.industry ?? '-'}</small>
              </button>
            ))}
          </div>
        </div>

        <div className="panel stock-detail-panel">
          <div className="panel-heading">
            <h2>{detail?.stock.name ?? '股票详情'}</h2>
            <span>{detail?.stock.ts_code ?? '-'}</span>
          </div>

          <div className="summary-grid">
            <SummaryItem label="地区" value={detail?.stock.area ?? '-'} />
            <SummaryItem label="行业" value={detail?.stock.industry ?? '-'} />
            <SummaryItem label="市场" value={detail?.stock.market ?? '-'} />
            <SummaryItem label="交易所" value={detail?.stock.exchange ?? '-'} />
            <SummaryItem label="上市状态" value={detail?.stock.list_status ?? '-'} />
            <SummaryItem label="上市日期" value={detail?.stock.list_date ?? '-'} />
          </div>

          <div className="quote-overview">
            <div>
              <span>最新收盘</span>
              <strong>{latestQuote?.close ?? '-'}</strong>
            </div>
            <div>
              <span>涨跌幅</span>
              <strong>{latestQuote?.pct_chg ?? '-'}</strong>
            </div>
            <div>
              <span>成交量</span>
              <strong>{latestQuote?.vol ?? '-'}</strong>
            </div>
          </div>

          <section className="stock-factor-section">
            <div className="panel-heading">
              <h2>基本面指标</h2>
              <span>{(detail?.factors.length ?? 0).toLocaleString('zh-CN')} 个最新指标</span>
            </div>
            <div className="stock-factor-grid">
              {(detail?.factors ?? []).map((factor) => (
                <div className="stock-factor-card" key={factor.factor_code}>
                  <span>{stockFactorLabel(factor.factor_code)}</span>
                  <strong>{formatNumber(factor.value)}</strong>
                  <small>
                    {factor.report_end_date ?? factor.factor_date} / {factor.factor_code}
                  </small>
                </div>
              ))}
              {(detail?.factors.length ?? 0) === 0 ? (
                <p className="empty-text">暂无基本面因子数据，请先在策略模块执行因子计算。</p>
              ) : null}
            </div>
          </section>

          <section className="stock-factor-section">
            <div className="panel-heading">
              <h2>指标趋势</h2>
              <span>最近 12 期</span>
            </div>
            <div className="factor-trend-list">
              {groupFactorHistory(detail?.factor_history ?? []).map((group) => (
                <article className="factor-trend-row" key={group.factorCode}>
                  <strong>{stockFactorLabel(group.factorCode)}</strong>
                  <div className="factor-trend-bars">
                    {group.points.map((point) => (
                      <span
                        key={`${group.factorCode}-${point.factor_date}`}
                        style={{ height: `${String(point.height)}%` }}
                        title={`${point.report_end_date ?? point.factor_date}: ${point.value}`}
                      />
                    ))}
                  </div>
                </article>
              ))}
            </div>
          </section>

          <div className="sparkline" aria-label="最近收盘价走势">
            {chartPoints.map((point) => (
              <span
                key={point.key}
                style={{ height: `${String(point.height)}%` }}
                title={`${point.key}: ${point.value}`}
              />
            ))}
          </div>

          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>交易日</th>
                  <th>开盘</th>
                  <th>最高</th>
                  <th>最低</th>
                  <th>收盘</th>
                  <th>涨跌幅</th>
                </tr>
              </thead>
              <tbody>
                {(detail?.quotes ?? []).slice(-10).map((quote) => (
                  <tr key={quote.trade_date}>
                    <td>{quote.trade_date}</td>
                    <td>{quote.open ?? '-'}</td>
                    <td>{quote.high ?? '-'}</td>
                    <td>{quote.low ?? '-'}</td>
                    <td>{quote.close ?? '-'}</td>
                    <td>{quote.pct_chg ?? '-'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </section>
    </section>
  );
}

function stockFactorLabel(code: string): string {
  const labels: Record<string, string> = {
    debt_to_assets: '资产负债率',
    dv_ttm: '股息率 TTM',
    grossprofit_margin: '毛利率',
    netprofit_margin: '净利率',
    netprofit_yoy: '净利润同比',
    ocf_to_profit: '现金流质量',
    or_yoy: '营收同比',
    pb: '市净率',
    pe_ttm: '市盈率 TTM',
    roe: 'ROE',
  };
  return labels[code] ?? code;
}

function formatNumber(value: string): string {
  const parsed = Number(value);
  if (!Number.isFinite(parsed)) {
    return value;
  }
  return parsed.toFixed(2);
}

function groupFactorHistory(points: StockDetail['factor_history']) {
  const groups = new Map<string, StockDetail['factor_history']>();
  for (const point of points) {
    const group = groups.get(point.factor_code) ?? [];
    group.push(point);
    groups.set(point.factor_code, group);
  }
  return [...groups.entries()].map(([factorCode, groupPoints]) => {
    const values = groupPoints.map((point) => Number(point.value)).filter(Number.isFinite);
    const min = Math.min(...values);
    const max = Math.max(...values);
    return {
      factorCode,
      points: groupPoints.map((point) => {
        const value = Number(point.value);
        const ratio = max === min ? 0.5 : (value - min) / (max - min);
        return {
          ...point,
          height: Number.isFinite(ratio) ? Math.max(8, Math.round(ratio * 100)) : 8,
        };
      }),
    };
  });
}

function SummaryItem(props: { label: string; value: string }) {
  return (
    <div className="summary-item">
      <span>{props.label}</span>
      <strong>{props.value}</strong>
    </div>
  );
}

function buildChartPoints(quotes: StockQuotePoint[]) {
  const values = quotes
    .map((quote) => Number(quote.close))
    .filter((value) => Number.isFinite(value) && value > 0);
  const min = Math.min(...values);
  const max = Math.max(...values);
  return quotes.slice(-60).map((quote) => {
    const value = Number(quote.close);
    const ratio = max === min ? 0.5 : (value - min) / (max - min);
    return {
      key: quote.trade_date,
      value: quote.close ?? '-',
      height: Number.isFinite(ratio) ? Math.max(8, Math.round(ratio * 100)) : 8,
    };
  });
}
