export function StrategiesPage() {
  return (
    <section className="workspace-panel">
      <header className="module-header">
        <div>
          <p className="eyebrow">Strategies</p>
          <h1>策略实验室</h1>
        </div>
      </header>
      <div className="placeholder-grid">
        <div className="panel">
          <div className="panel-heading">
            <h2>策略列表</h2>
            <span>待接入</span>
          </div>
          <p className="empty-text">选股条件、参数版本和启停状态。</p>
        </div>
        <div className="panel">
          <div className="panel-heading">
            <h2>因子条件</h2>
            <span>待接入</span>
          </div>
          <p className="empty-text">估值、动量、成交、财务和风险过滤。</p>
        </div>
      </div>
    </section>
  );
}
