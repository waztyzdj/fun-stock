export function BacktestsPage() {
  return (
    <section className="workspace-panel">
      <header className="module-header">
        <div>
          <p className="eyebrow">Backtests</p>
          <h1>回测中心</h1>
        </div>
      </header>
      <div className="placeholder-grid">
        <div className="panel">
          <div className="panel-heading">
            <h2>任务队列</h2>
            <span>待接入</span>
          </div>
          <p className="empty-text">任务状态、回测区间、基准和资金曲线。</p>
        </div>
        <div className="panel">
          <div className="panel-heading">
            <h2>绩效报告</h2>
            <span>待接入</span>
          </div>
          <p className="empty-text">收益、回撤、胜率、换手和持仓明细。</p>
        </div>
      </div>
    </section>
  );
}
