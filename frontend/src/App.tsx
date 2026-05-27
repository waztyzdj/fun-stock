import { useEffect, useState } from 'react';

import { BacktestsPage } from './features/backtests/BacktestsPage';
import { DataQualityPage } from './features/data-quality/DataQualityPage';
import { DataSyncPage } from './features/data-sync/DataSyncPage';
import { StocksPage } from './features/stocks/StocksPage';
import { StrategiesPage } from './features/strategies/StrategiesPage';
import { type AppRoute, navigationItems, routeFromHash } from './app/navigation';

import './styles.css';

export function App() {
  const [activeRoute, setActiveRoute] = useState<AppRoute>(() => routeFromHash(window.location.hash));

  useEffect(() => {
    function handleHashChange() {
      setActiveRoute(routeFromHash(window.location.hash));
    }
    window.addEventListener('hashchange', handleHashChange);
    return () => {
      window.removeEventListener('hashchange', handleHashChange);
    };
  }, []);

  return (
    <div className="app-layout">
      <aside className="sidebar" aria-label="主导航">
        <div className="brand-block">
          <strong>Fun Stock</strong>
          <span>量化研究平台</span>
        </div>
        <nav className="nav-list">
          {navigationItems.map((item) => (
            <a
              aria-current={activeRoute === item.route ? 'page' : undefined}
              className="nav-link"
              href={`#/${item.route}`}
              key={item.route}
            >
              <span>{item.label}</span>
              <small>{item.group}</small>
            </a>
          ))}
        </nav>
      </aside>

      <main className="main-shell">
        <Topbar activeRoute={activeRoute} />
        <div className="page-content">{renderRoute(activeRoute)}</div>
      </main>
    </div>
  );
}

function Topbar(props: { activeRoute: AppRoute }) {
  const activeItem = navigationItems.find((item) => item.route === props.activeRoute);

  return (
    <header className="app-topbar">
      <div>
        <p className="eyebrow">Workspace</p>
        <h2>{activeItem?.label ?? '数据同步'}</h2>
      </div>
      <div className="topbar-meta">
        <span>本地环境</span>
        <strong>127.0.0.1:5175</strong>
      </div>
    </header>
  );
}

function renderRoute(route: AppRoute) {
  if (route === 'stocks') {
    return <StocksPage />;
  }
  if (route === 'strategies') {
    return <StrategiesPage />;
  }
  if (route === 'backtests') {
    return <BacktestsPage />;
  }
  if (route === 'quality') {
    return <DataQualityPage />;
  }
  return <DataSyncPage />;
}
