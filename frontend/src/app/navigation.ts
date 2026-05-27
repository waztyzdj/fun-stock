export type AppRoute = 'sync' | 'stocks' | 'strategies' | 'backtests' | 'quality';

export interface NavigationItem {
  route: AppRoute;
  label: string;
  group: string;
}

export const navigationItems: NavigationItem[] = [
  { route: 'sync', label: '数据同步', group: '数据' },
  { route: 'quality', label: '数据质量', group: '数据' },
  { route: 'stocks', label: '股票中心', group: '研究' },
  { route: 'strategies', label: '策略实验室', group: '研究' },
  { route: 'backtests', label: '回测中心', group: '执行' },
];

export function routeFromHash(hash: string): AppRoute {
  const route = hash.replace(/^#\/?/, '');
  if (route === 'stocks' || route === 'strategies' || route === 'backtests' || route === 'quality') {
    return route;
  }
  return 'sync';
}
