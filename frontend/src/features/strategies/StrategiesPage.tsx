import { useEffect, useMemo, useState } from 'react';

import {
  buildFactorValues,
  fetchFactorBuildStatus,
  fetchFactorQuality,
  fetchStrategies,
  fetchStrategyFactors,
  saveStrategy,
  screenStrategy,
} from '../../services/apiClient';
import type {
  FactorBuildResult,
  FactorBuildStatus,
  FactorDefinition,
  FactorQualityItem,
  StrategyFilter,
  StrategyListItem,
  StrategyOperator,
  StrategyScreenItem,
  StrategyScreenResult,
  StrategySort,
  StrategyUniverse,
} from '../../types/strategies';

type StrategyView = 'build' | 'quality' | 'wizard' | 'factors' | 'saved';

const operatorOptions: StrategyOperator[] = ['>=', '<=', '>', '<', '='];
const today = new Date().toISOString().slice(0, 10);

const categoryLabels: Record<string, string> = {
  cash_flow: '现金流质量',
  growth: '成长能力',
  profitability: '盈利能力',
  safety: '财务安全',
  valuation: '估值水平',
};

const presetStrategies = [
  {
    name: '质量现金流',
    description: '盈利能力、现金流质量和负债约束优先',
    filters: [
      { factor_code: 'roe', operator: '>=', value: '12' },
      { factor_code: 'ocf_to_profit', operator: '>=', value: '80' },
      { factor_code: 'debt_to_assets', operator: '<=', value: '60' },
    ] satisfies StrategyFilter[],
    sort: [
      { factor_code: 'roe', direction: 'desc' },
      { factor_code: 'ocf_to_profit', direction: 'desc' },
    ] satisfies StrategySort[],
  },
  {
    name: '稳健低估',
    description: '估值不贵，同时保留盈利和安全边际',
    filters: [
      { factor_code: 'pe_ttm', operator: '<=', value: '35' },
      { factor_code: 'pb', operator: '<=', value: '4' },
      { factor_code: 'roe', operator: '>=', value: '10' },
      { factor_code: 'debt_to_assets', operator: '<=', value: '65' },
    ] satisfies StrategyFilter[],
    sort: [
      { factor_code: 'pe_ttm', direction: 'asc' },
      { factor_code: 'roe', direction: 'desc' },
    ] satisfies StrategySort[],
  },
  {
    name: '成长质量',
    description: '收入和利润增长要有质量支撑',
    filters: [
      { factor_code: 'or_yoy', operator: '>=', value: '8' },
      { factor_code: 'netprofit_yoy', operator: '>=', value: '8' },
      { factor_code: 'grossprofit_margin', operator: '>=', value: '25' },
    ] satisfies StrategyFilter[],
    sort: [
      { factor_code: 'or_yoy', direction: 'desc' },
      { factor_code: 'roe', direction: 'desc' },
    ] satisfies StrategySort[],
  },
];

const defaultUniverse: StrategyUniverse = {
  exclude_st: true,
  min_list_years: 3,
};

export function StrategiesPage() {
  const [activeView, setActiveView] = useState<StrategyView>('build');
  const [factors, setFactors] = useState<FactorDefinition[]>([]);
  const [buildStatus, setBuildStatus] = useState<FactorBuildStatus | null>(null);
  const [qualityItems, setQualityItems] = useState<FactorQualityItem[]>([]);
  const [strategies, setStrategies] = useState<StrategyListItem[]>([]);
  const [universe, setUniverse] = useState<StrategyUniverse>(defaultUniverse);
  const [filters, setFilters] = useState<StrategyFilter[]>(presetStrategies[0].filters);
  const [sort, setSort] = useState<StrategySort[]>(presetStrategies[0].sort);
  const [asOfDate, setAsOfDate] = useState(today);
  const [limit, setLimit] = useState(50);
  const [strategyName, setStrategyName] = useState('长期基本面质量策略');
  const [strategyDescription, setStrategyDescription] = useState(presetStrategies[0].description);
  const [screenResult, setScreenResult] = useState<StrategyScreenResult | null>(null);
  const [lastBuildResult, setLastBuildResult] = useState<FactorBuildResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [factorBuilding, setFactorBuilding] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    Promise.all([
      fetchStrategyFactors(controller.signal),
      fetchFactorBuildStatus(controller.signal),
      fetchFactorQuality(controller.signal),
      fetchStrategies(controller.signal),
    ])
      .then(([factorItems, nextBuildStatus, nextQualityItems, strategyItems]) => {
        setFactors(factorItems);
        setBuildStatus(nextBuildStatus);
        setQualityItems(nextQualityItems);
        setStrategies(strategyItems);
      })
      .catch((loadError: unknown) => {
        if (loadError instanceof DOMException && loadError.name === 'AbortError') {
          return;
        }
        setError(loadError instanceof Error ? loadError.message : 'Unknown error');
      });
    return () => {
      controller.abort();
    };
  }, []);

  const factorByCode = useMemo(
    () => new Map(factors.map((factor) => [factor.code, factor])),
    [factors],
  );

  const factorGroups = useMemo(() => groupFactorsByCategory(factors), [factors]);
  const availableFactors = factors.length > 0 ? factors : fallbackFactors;
  const latestFactorDate = latestDate(factors.map((factor) => factor.latest_factor_date));
  const factorsWithData = factors.filter((factor) => factor.value_count > 0).length;
  const readyQualityCount = qualityItems.filter((item) => item.status === 'ready').length;

  async function refreshFactorRuntime() {
    setError(null);
    const [nextFactors, nextBuildStatus, nextQualityItems] = await Promise.all([
      fetchStrategyFactors(),
      fetchFactorBuildStatus(),
      fetchFactorQuality(),
    ]);
    setFactors(nextFactors);
    setBuildStatus(nextBuildStatus);
    setQualityItems(nextQualityItems);
  }

  async function runFactorBuild(startDate: string | null) {
    setFactorBuilding(true);
    setError(null);
    setNotice(null);
    try {
      const result = await buildFactorValues({ startDate });
      setLastBuildResult(result);
      setBuildStatus(result.status);
      await refreshFactorRuntime();
      setNotice(`因子计算完成，写入或更新 ${result.rows.toLocaleString('zh-CN')} 行。`);
    } catch (buildError) {
      setError(buildError instanceof Error ? buildError.message : 'Unknown error');
    } finally {
      setFactorBuilding(false);
    }
  }

  async function runScreen() {
    setLoading(true);
    setError(null);
    setNotice(null);
    try {
      const result = await screenStrategy(buildRequest());
      setScreenResult(result);
      setNotice(`筛选完成，命中 ${result.total.toLocaleString('zh-CN')} 只股票。`);
    } catch (screenError) {
      setError(screenError instanceof Error ? screenError.message : 'Unknown error');
    } finally {
      setLoading(false);
    }
  }

  async function saveCurrentStrategy() {
    setSaving(true);
    setError(null);
    setNotice(null);
    try {
      const result = await saveStrategy({
        name: strategyName,
        description: strategyDescription,
        request: buildRequest(),
      });
      setNotice(`策略「${result.name}」已保存。`);
      setStrategies(await fetchStrategies());
      setActiveView('saved');
    } catch (saveError) {
      setError(saveError instanceof Error ? saveError.message : 'Unknown error');
    } finally {
      setSaving(false);
    }
  }

  function buildRequest() {
    return {
      as_of_date: asOfDate || null,
      filters,
      limit,
      sort,
      universe,
    };
  }

  return (
    <section className="workspace-panel strategy-page">
      <header className="module-header">
        <div>
          <p className="eyebrow">Strategies</p>
          <h1>基本面策略实验室</h1>
        </div>
        <div className="strategy-tabs" role="tablist" aria-label="策略模块视图">
          <button
            aria-selected={activeView === 'build'}
            data-active={activeView === 'build'}
            onClick={() => {
              setActiveView('build');
            }}
            type="button"
          >
            因子生产
          </button>
          <button
            aria-selected={activeView === 'quality'}
            data-active={activeView === 'quality'}
            onClick={() => {
              setActiveView('quality');
            }}
            type="button"
          >
            质量巡检
          </button>
          <button
            aria-selected={activeView === 'wizard'}
            data-active={activeView === 'wizard'}
            onClick={() => {
              setActiveView('wizard');
            }}
            type="button"
          >
            选股向导
          </button>
          <button
            aria-selected={activeView === 'factors'}
            data-active={activeView === 'factors'}
            onClick={() => {
              setActiveView('factors');
            }}
            type="button"
          >
            因子字典
          </button>
          <button
            aria-selected={activeView === 'saved'}
            data-active={activeView === 'saved'}
            onClick={() => {
              setActiveView('saved');
            }}
            type="button"
          >
            已保存策略
          </button>
        </div>
      </header>

      {error ? <p className="error-banner">策略模块读取失败：{error}</p> : null}
      {notice ? <p className="success-banner">{notice}</p> : null}

      <section className="strategy-dashboard" aria-label="策略概览">
        <MetricCard label="因子总数" value={(buildStatus?.factor_count ?? factors.length).toLocaleString('zh-CN')} />
        <MetricCard label="有数据因子" value={factorsWithData.toLocaleString('zh-CN')} />
        <MetricCard label="可用因子" value={readyQualityCount.toLocaleString('zh-CN')} />
        <MetricCard label="最新因子日期" value={buildStatus?.latest_factor_date ?? latestFactorDate ?? '-'} />
        <MetricCard label="筛选结果" value={(screenResult?.total ?? 0).toLocaleString('zh-CN')} />
      </section>

      {activeView === 'build' ? (
        <FactorBuildView
          buildStatus={buildStatus}
          factorBuilding={factorBuilding}
          lastResult={lastBuildResult}
          onBuild={(startDate) => void runFactorBuild(startDate)}
          onRefresh={() => void refreshFactorRuntime()}
        />
      ) : null}

      {activeView === 'quality' ? (
        <FactorQualityView items={qualityItems} />
      ) : null}

      {activeView === 'wizard' ? (
        <WizardView
          availableFactors={availableFactors}
          factorByCode={factorByCode}
          filters={filters}
          limit={limit}
          loading={loading}
          saving={saving}
          screenResult={screenResult}
          sort={sort}
          strategyDescription={strategyDescription}
          strategyName={strategyName}
          universe={universe}
          asOfDate={asOfDate}
          onApplyPreset={(preset) => {
            setFilters(preset.filters);
            setSort(preset.sort);
            setStrategyDescription(preset.description);
            setStrategyName(`长期基本面${preset.name}策略`);
          }}
          onAsOfDateChange={setAsOfDate}
          onFilterAdd={() => {
            setFilters([...filters, newFilter(availableFactors)]);
          }}
          onFilterChange={(index, nextFilter) => {
            setFilters(filters.map((filter, itemIndex) => (itemIndex === index ? nextFilter : filter)));
          }}
          onFilterRemove={(index) => {
            setFilters(filters.filter((_, itemIndex) => itemIndex !== index));
          }}
          onLimitChange={setLimit}
          onRunScreen={() => void runScreen()}
          onSaveStrategy={() => void saveCurrentStrategy()}
          onSortAdd={() => {
            setSort([...sort, newSort(availableFactors)]);
          }}
          onSortChange={(index, nextSort) => {
            setSort(sort.map((sortItem, itemIndex) => (itemIndex === index ? nextSort : sortItem)));
          }}
          onSortRemove={(index) => {
            setSort(sort.filter((_, itemIndex) => itemIndex !== index));
          }}
          onStrategyDescriptionChange={setStrategyDescription}
          onStrategyNameChange={setStrategyName}
          onUniverseChange={setUniverse}
        />
      ) : null}

      {activeView === 'factors' ? (
        <FactorsView factorGroups={factorGroups} />
      ) : null}

      {activeView === 'saved' ? (
        <SavedStrategiesView strategies={strategies} />
      ) : null}
    </section>
  );
}

interface FactorBuildViewProps {
  buildStatus: FactorBuildStatus | null;
  factorBuilding: boolean;
  lastResult: FactorBuildResult | null;
  onBuild: (startDate: string | null) => void;
  onRefresh: () => void;
}

function FactorBuildView({
  buildStatus,
  factorBuilding,
  lastResult,
  onBuild,
  onRefresh,
}: FactorBuildViewProps) {
  const [incrementalStartDate, setIncrementalStartDate] = useState('');

  return (
    <section className="factor-ops-layout">
      <div className="panel factor-ops-main">
        <div className="panel-heading">
          <h2>因子计算任务控制台</h2>
          <span>把 Tushare 原始数据转换成可用于选股的因子值</span>
        </div>
        <div className="factor-build-status">
          <StatusBlock label="最近计算时间" value={formatDateTime(buildStatus?.latest_updated_at)} />
          <StatusBlock label="最新因子日期" value={buildStatus?.latest_factor_date ?? '-'} />
          <StatusBlock label="最新财报期" value={buildStatus?.latest_report_end_date ?? '-'} />
          <StatusBlock label="因子值行数" value={(buildStatus?.total_value_count ?? 0).toLocaleString('zh-CN')} />
          <StatusBlock label="覆盖股票数" value={(buildStatus?.stock_count ?? 0).toLocaleString('zh-CN')} />
          <StatusBlock label="已产出因子" value={(buildStatus?.factor_count ?? 0).toLocaleString('zh-CN')} />
        </div>
        {lastResult ? (
          <p className="factor-build-note">
            上次手动计算写入或更新 {lastResult.rows.toLocaleString('zh-CN')} 行，起始日期：
            {lastResult.start_date ?? '全量'}。
          </p>
        ) : (
          <p className="factor-build-note">
            建议在 Tushare 财务和日指标回填完成后先跑一次全量计算；后续日常使用增量计算即可。
          </p>
        )}
      </div>

      <aside className="panel factor-ops-side">
        <div className="panel-heading">
          <h2>手动触发</h2>
          <span>{factorBuilding ? '计算中' : '空闲'}</span>
        </div>
        <label>
          <span>增量起始日期</span>
          <input
            type="date"
            value={incrementalStartDate}
            onChange={(event) => {
              setIncrementalStartDate(event.target.value);
            }}
          />
        </label>
        <div className="button-row">
          <button
            className="primary-button"
            disabled={factorBuilding}
            type="button"
            onClick={() => {
              onBuild(incrementalStartDate || null);
            }}
          >
            {factorBuilding ? '计算中' : '增量计算'}
          </button>
          <button
            className="secondary-button"
            disabled={factorBuilding}
            type="button"
            onClick={() => {
              onBuild(null);
            }}
          >
            全量计算
          </button>
        </div>
        <button className="secondary-button" disabled={factorBuilding} type="button" onClick={onRefresh}>
          刷新状态
        </button>
      </aside>
    </section>
  );
}

function FactorQualityView({ items }: { items: FactorQualityItem[] }) {
  const readyCount = items.filter((item) => item.status === 'ready').length;
  const warningCount = items.filter((item) => item.status === 'warning').length;
  const emptyCount = items.filter((item) => item.status === 'empty').length;
  const sortedItems = [...items].sort((first, second) => qualityWeight(first) - qualityWeight(second));

  return (
    <section className="panel strategy-explain-panel">
      <div className="panel-heading">
        <h2>因子质量巡检</h2>
        <span>先看覆盖率，再决定是否进入选股</span>
      </div>
      <div className="factor-quality-summary">
        <StatusBlock label="可用" value={readyCount.toLocaleString('zh-CN')} />
        <StatusBlock label="需关注" value={warningCount.toLocaleString('zh-CN')} />
        <StatusBlock label="无数据" value={emptyCount.toLocaleString('zh-CN')} />
      </div>
      <div className="factor-quality-list">
        {sortedItems.map((item) => (
          <article className="factor-quality-row" key={item.factor_code}>
            <div>
              <strong>{item.factor_name}</strong>
              <span>
                {categoryLabel(item.category)} · {item.factor_code}
              </span>
            </div>
            <span className="status-badge" data-status={qualityStatusTone(item.status)}>
              {qualityStatusLabel(item.status)}
            </span>
            <div>
              <strong>{formatPercent(item.coverage_ratio)}</strong>
              <span>
                覆盖 {item.stock_count.toLocaleString('zh-CN')} /{' '}
                {item.universe_stock_count.toLocaleString('zh-CN')}
              </span>
            </div>
            <div>
              <strong>{item.latest_factor_date ?? '-'}</strong>
              <span>最新日期，最新覆盖 {item.latest_value_count.toLocaleString('zh-CN')}</span>
            </div>
            <div>
              <strong>{item.value_count.toLocaleString('zh-CN')}</strong>
              <span>
                零值 {item.zero_value_count.toLocaleString('zh-CN')}，负值{' '}
                {item.negative_value_count.toLocaleString('zh-CN')}
              </span>
            </div>
          </article>
        ))}
        {items.length === 0 ? <p className="empty-text">暂无因子质量数据。</p> : null}
      </div>
    </section>
  );
}

function StatusBlock(props: { label: string; value: string }) {
  return (
    <div className="status-block">
      <span>{props.label}</span>
      <strong>{props.value}</strong>
    </div>
  );
}

interface WizardViewProps {
  availableFactors: FactorDefinition[];
  factorByCode: Map<string, FactorDefinition>;
  filters: StrategyFilter[];
  limit: number;
  loading: boolean;
  saving: boolean;
  screenResult: StrategyScreenResult | null;
  sort: StrategySort[];
  strategyDescription: string;
  strategyName: string;
  universe: StrategyUniverse;
  asOfDate: string;
  onApplyPreset: (preset: (typeof presetStrategies)[number]) => void;
  onAsOfDateChange: (value: string) => void;
  onFilterAdd: () => void;
  onFilterChange: (index: number, filter: StrategyFilter) => void;
  onFilterRemove: (index: number) => void;
  onLimitChange: (value: number) => void;
  onRunScreen: () => void;
  onSaveStrategy: () => void;
  onSortAdd: () => void;
  onSortChange: (index: number, sort: StrategySort) => void;
  onSortRemove: (index: number) => void;
  onStrategyDescriptionChange: (value: string) => void;
  onStrategyNameChange: (value: string) => void;
  onUniverseChange: (value: StrategyUniverse) => void;
}

function WizardView(props: WizardViewProps) {
  return (
    <>
      <section className="strategy-layout">
        <div className="strategy-builder">
          <div className="panel">
            <div className="panel-heading">
              <h2>1. 选择股票池</h2>
              <span>先限定长期投资的基础范围</span>
            </div>
            <div className="strategy-control-grid">
              <label className="toggle-row">
                <input
                  checked={props.universe.exclude_st}
                  type="checkbox"
                  onChange={(event) => {
                    props.onUniverseChange({
                      ...props.universe,
                      exclude_st: event.target.checked,
                    });
                  }}
                />
                <span>排除 ST 股票</span>
              </label>
              <label>
                <span>最少上市年限</span>
                <input
                  min="0"
                  type="number"
                  value={props.universe.min_list_years ?? ''}
                  onChange={(event) => {
                    props.onUniverseChange({
                      ...props.universe,
                      min_list_years: parseOptionalNumber(event.target.value),
                    });
                  }}
                />
              </label>
              <label>
                <span>观察日期</span>
                <input
                  type="date"
                  value={props.asOfDate}
                  onChange={(event) => {
                    props.onAsOfDateChange(event.target.value);
                  }}
                />
              </label>
              <label>
                <span>返回数量</span>
                <input
                  max="200"
                  min="1"
                  type="number"
                  value={props.limit}
                  onChange={(event) => {
                    props.onLimitChange(clampNumber(event.target.value, 1, 200));
                  }}
                />
              </label>
            </div>
          </div>

          <div className="panel">
            <div className="panel-heading">
              <h2>2. 设置筛选条件</h2>
              <button className="secondary-button compact-button" type="button" onClick={props.onFilterAdd}>
                新增条件
              </button>
            </div>
            <div className="strategy-rule-list">
              {props.filters.map((filter, index) => (
                <FilterRow
                  availableFactors={props.availableFactors}
                  filter={filter}
                  key={`${filter.factor_code}-${String(index)}`}
                  onChange={(nextFilter) => {
                    props.onFilterChange(index, nextFilter);
                  }}
                  onRemove={() => {
                    props.onFilterRemove(index);
                  }}
                />
              ))}
            </div>
          </div>

          <div className="panel">
            <div className="panel-heading">
              <h2>3. 设置排序</h2>
              <button className="secondary-button compact-button" type="button" onClick={props.onSortAdd}>
                新增排序
              </button>
            </div>
            <div className="strategy-rule-list compact-list">
              {props.sort.map((sortItem, index) => (
                <SortRow
                  availableFactors={props.availableFactors}
                  key={`${sortItem.factor_code}-${String(index)}`}
                  sort={sortItem}
                  onChange={(nextSort) => {
                    props.onSortChange(index, nextSort);
                  }}
                  onRemove={() => {
                    props.onSortRemove(index);
                  }}
                />
              ))}
            </div>
          </div>
        </div>

        <aside className="strategy-side">
          <div className="panel">
            <div className="panel-heading">
              <h2>策略模板</h2>
              <span>适合长线基本面初筛</span>
            </div>
            <div className="preset-row">
              {presetStrategies.map((preset) => (
                <button
                  className="preset-button"
                  key={preset.name}
                  type="button"
                  onClick={() => {
                    props.onApplyPreset(preset);
                  }}
                >
                  <strong>{preset.name}</strong>
                  <span>{preset.description}</span>
                </button>
              ))}
            </div>
          </div>

          <div className="panel">
            <div className="panel-heading">
              <h2>保存策略</h2>
              <span>保存为草稿，后续用于回测</span>
            </div>
            <div className="save-strategy-form">
              <label>
                <span>策略名称</span>
                <input
                  value={props.strategyName}
                  onChange={(event) => {
                    props.onStrategyNameChange(event.target.value);
                  }}
                />
              </label>
              <label>
                <span>策略说明</span>
                <textarea
                  rows={4}
                  value={props.strategyDescription}
                  onChange={(event) => {
                    props.onStrategyDescriptionChange(event.target.value);
                  }}
                />
              </label>
              <div className="button-row">
                <button className="primary-button" disabled={props.loading} type="button" onClick={props.onRunScreen}>
                  {props.loading ? '筛选中' : '运行筛选'}
                </button>
                <button
                  className="secondary-button"
                  disabled={props.saving || props.strategyName.trim().length === 0}
                  type="button"
                  onClick={props.onSaveStrategy}
                >
                  {props.saving ? '保存中' : '保存策略'}
                </button>
              </div>
            </div>
          </div>
        </aside>
      </section>

        <ResultsPanel
          factorByCode={props.factorByCode}
          filters={props.filters}
          items={props.screenResult?.items ?? []}
          nearMisses={props.screenResult?.near_misses ?? []}
          total={props.screenResult?.total ?? 0}
        />
    </>
  );
}

interface FilterRowProps {
  availableFactors: FactorDefinition[];
  filter: StrategyFilter;
  onChange: (filter: StrategyFilter) => void;
  onRemove: () => void;
}

function FilterRow({ availableFactors, filter, onChange, onRemove }: FilterRowProps) {
  return (
    <div className="strategy-rule-row">
      <select
        aria-label="筛选因子"
        value={filter.factor_code}
        onChange={(event) => {
          onChange({ ...filter, factor_code: event.target.value });
        }}
      >
        {availableFactors.map((factor) => (
          <option key={factor.code} value={factor.code}>
            {factor.name}
          </option>
        ))}
      </select>
      <select
        aria-label="筛选关系"
        value={filter.operator}
        onChange={(event) => {
          onChange({ ...filter, operator: event.target.value as StrategyOperator });
        }}
      >
        {operatorOptions.map((operator) => (
          <option key={operator} value={operator}>
            {operator}
          </option>
        ))}
      </select>
      <input
        aria-label="筛选阈值"
        value={filter.value}
        onChange={(event) => {
          onChange({ ...filter, value: event.target.value });
        }}
      />
      <button className="secondary-button icon-text-button" type="button" onClick={onRemove}>
        删除
      </button>
    </div>
  );
}

interface SortRowProps {
  availableFactors: FactorDefinition[];
  sort: StrategySort;
  onChange: (sort: StrategySort) => void;
  onRemove: () => void;
}

function SortRow({ availableFactors, sort, onChange, onRemove }: SortRowProps) {
  return (
    <div className="strategy-rule-row sort-row">
      <select
        aria-label="排序因子"
        value={sort.factor_code}
        onChange={(event) => {
          onChange({ ...sort, factor_code: event.target.value });
        }}
      >
        {availableFactors.map((factor) => (
          <option key={factor.code} value={factor.code}>
            {factor.name}
          </option>
        ))}
      </select>
      <select
        aria-label="排序方向"
        value={sort.direction}
        onChange={(event) => {
          onChange({ ...sort, direction: event.target.value === 'asc' ? 'asc' : 'desc' });
        }}
      >
        <option value="desc">从高到低</option>
        <option value="asc">从低到高</option>
      </select>
      <button className="secondary-button icon-text-button" type="button" onClick={onRemove}>
        删除
      </button>
    </div>
  );
}

interface FactorsViewProps {
  factorGroups: {
    category: string;
    factors: FactorDefinition[];
  }[];
}

function FactorsView({ factorGroups }: FactorsViewProps) {
  return (
    <section className="panel strategy-explain-panel">
      <div className="panel-heading">
        <h2>因子字典与口径说明</h2>
        <span>每个因子的来源、口径和覆盖度</span>
      </div>
      <div className="factor-card-grid">
        {factorGroups.map((group) => (
          <section className="factor-group" key={group.category}>
            <div className="factor-group-heading">
              <h3>{categoryLabel(group.category)}</h3>
              <span>{group.factors.length.toLocaleString('zh-CN')} 个因子</span>
            </div>
            <div className="factor-card-list">
              {group.factors.map((factor) => (
                <article className="factor-card" key={factor.code}>
                  <header>
                    <div>
                      <strong>{factor.name}</strong>
                      <span>{factor.code}</span>
                    </div>
                    <small>{factor.unit ?? '无单位'}</small>
                  </header>
                  <p>{factor.description}</p>
                  <dl className="factor-meta-grid">
                    <div>
                      <dt>计算口径</dt>
                      <dd>{factor.calculation_method}</dd>
                    </div>
                    <div>
                      <dt>数据来源</dt>
                      <dd>{factor.source}</dd>
                    </div>
                    <div>
                      <dt>频率</dt>
                      <dd>{periodTypeLabel(factor.period_type)}</dd>
                    </div>
                    <div>
                      <dt>默认方向</dt>
                      <dd>{factor.sort_direction === 'asc' ? '越低越好' : '越高越好'}</dd>
                    </div>
                  </dl>
                  <div className="factor-coverage-row">
                    <CoverageChip label="数据行" value={factor.value_count.toLocaleString('zh-CN')} />
                    <CoverageChip label="股票数" value={factor.stock_count.toLocaleString('zh-CN')} />
                    <CoverageChip label="最新日期" value={factor.latest_factor_date ?? '-'} />
                    <CoverageChip label="最新覆盖" value={factor.latest_value_count.toLocaleString('zh-CN')} />
                  </div>
                </article>
              ))}
            </div>
          </section>
        ))}
      </div>
    </section>
  );
}

function SavedStrategiesView({ strategies }: { strategies: StrategyListItem[] }) {
  return (
    <section className="panel">
      <div className="panel-heading">
        <h2>已保存策略</h2>
        <span>{strategies.length.toLocaleString('zh-CN')} 个草稿</span>
      </div>
      <div className="strategy-list">
        {strategies.map((strategy) => (
          <article className="strategy-list-item" key={strategy.id}>
            <div>
              <strong>{strategy.name}</strong>
              <span>{strategy.description ?? '暂无说明'}</span>
            </div>
            <small>{statusLabel(strategy.status)}</small>
          </article>
        ))}
        {strategies.length === 0 ? <p className="empty-text">还没有保存的策略。</p> : null}
      </div>
    </section>
  );
}

interface ResultsPanelProps {
  factorByCode: Map<string, FactorDefinition>;
  filters: StrategyFilter[];
  items: StrategyScreenItem[];
  nearMisses: StrategyScreenItem[];
  total: number;
}

function ResultsPanel({ factorByCode, filters, items, nearMisses, total }: ResultsPanelProps) {
  return (
    <section className="panel strategy-result-panel">
      <div className="panel-heading">
        <h2>筛选结果</h2>
        <span>{total.toLocaleString('zh-CN')} 只股票</span>
      </div>
      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th>股票</th>
              <th>行业</th>
              <th>市场</th>
              <th>上市日期</th>
              <th>策略分数</th>
              <th>关键因子</th>
              <th>命中解释</th>
            </tr>
          </thead>
          <tbody>
            {items.map((item) => (
              <tr key={item.ts_code}>
                <td>
                  <strong>{item.name}</strong>
                  <small>{item.ts_code}</small>
                </td>
                <td>{item.industry ?? '-'}</td>
                <td>{item.market ?? '-'}</td>
                <td>{item.list_date ?? '-'}</td>
                <td>{formatDecimal(item.score, 2)}</td>
                <td>
                  <div className="result-factor-list">
                    {item.factor_values.map((factorValue) => (
                      <span key={`${item.ts_code}-${factorValue.factor_code}`}>
                        {factorByCode.get(factorValue.factor_code)?.name ?? factorValue.factor_code}：
                        {formatDecimal(factorValue.value, 2)}
                      </span>
                    ))}
                  </div>
                </td>
                <td>
                  <div className="result-explain-list">
                    {item.filter_evaluations.map((evaluation) => (
                      <span
                        data-passed={evaluation.passed}
                        key={`${item.ts_code}-${evaluation.factor_code}-${evaluation.operator}`}
                      >
                        {factorByCode.get(evaluation.factor_code)?.name ?? evaluation.factor_code}{' '}
                        {evaluation.operator} {evaluation.threshold}，实际{' '}
                        {evaluation.value ? formatDecimal(evaluation.value, 2) : '缺失'}
                      </span>
                    ))}
                  </div>
                </td>
              </tr>
            ))}
            {items.length === 0 ? (
              <tr>
                <td colSpan={7}>
                  <span className="empty-text">
                    运行筛选后展示结果。当前条件：{filters.length.toLocaleString('zh-CN')} 个筛选因子。
                  </span>
                </td>
              </tr>
            ) : null}
          </tbody>
        </table>
      </div>
      {nearMisses.length > 0 ? (
        <div className="near-miss-panel">
          <div className="panel-heading">
            <h3>接近入选但未命中</h3>
            <span>{nearMisses.length.toLocaleString('zh-CN')} 只股票</span>
          </div>
          <div className="near-miss-list">
            {nearMisses.map((item) => (
              <article className="near-miss-item" key={item.ts_code}>
                <strong>
                  {item.name} <small>{item.ts_code}</small>
                </strong>
                <div className="result-explain-list">
                  {item.filter_evaluations
                    .filter((evaluation) => !evaluation.passed)
                    .map((evaluation) => (
                      <span data-passed={false} key={`${item.ts_code}-${evaluation.factor_code}`}>
                        差一点：{factorByCode.get(evaluation.factor_code)?.name ?? evaluation.factor_code}{' '}
                        {evaluation.operator} {evaluation.threshold}，实际{' '}
                        {evaluation.value ? formatDecimal(evaluation.value, 2) : '缺失'}
                      </span>
                    ))}
                </div>
              </article>
            ))}
          </div>
        </div>
      ) : null}
    </section>
  );
}

function MetricCard(props: { label: string; value: string }) {
  return (
    <div className="metric-card">
      <span>{props.label}</span>
      <strong>{props.value}</strong>
    </div>
  );
}

function CoverageChip(props: { label: string; value: string }) {
  return (
    <span className="coverage-chip">
      <small>{props.label}</small>
      <strong>{props.value}</strong>
    </span>
  );
}

function groupFactorsByCategory(factors: FactorDefinition[]) {
  const groups = new Map<string, FactorDefinition[]>();
  for (const factor of factors) {
    const group = groups.get(factor.category) ?? [];
    group.push(factor);
    groups.set(factor.category, group);
  }
  return [...groups.entries()].map(([category, groupFactors]) => ({
    category,
    factors: groupFactors,
  }));
}

function newFilter(factors: FactorDefinition[]): StrategyFilter {
  if (factors.length === 0) {
    return {
      factor_code: 'roe',
      operator: '>=',
      value: '',
    };
  }
  return {
    factor_code: factors[0].code,
    operator: '>=',
    value: '',
  };
}

function newSort(factors: FactorDefinition[]): StrategySort {
  if (factors.length === 0) {
    return {
      factor_code: 'roe',
      direction: 'desc',
    };
  }
  const factor = factors[0];
  return {
    factor_code: factor.code,
    direction: factor.sort_direction === 'asc' ? 'asc' : 'desc',
  };
}

function categoryLabel(category: string): string {
  return categoryLabels[category] ?? category;
}

function periodTypeLabel(periodType: string): string {
  if (periodType === 'daily') {
    return '日频';
  }
  if (periodType === 'report') {
    return '财报期';
  }
  return periodType;
}

function statusLabel(status: string): string {
  if (status === 'draft') {
    return '草稿';
  }
  if (status === 'active') {
    return '启用';
  }
  return status;
}

function qualityStatusLabel(status: FactorQualityItem['status']): string {
  if (status === 'ready') {
    return '可用';
  }
  if (status === 'warning') {
    return '需关注';
  }
  return '无数据';
}

function qualityStatusTone(status: FactorQualityItem['status']): string {
  if (status === 'ready') {
    return 'success';
  }
  if (status === 'warning') {
    return 'warning';
  }
  return 'danger';
}

function qualityWeight(item: FactorQualityItem): number {
  if (item.status === 'empty') {
    return 0;
  }
  if (item.status === 'warning') {
    return 1;
  }
  return 2;
}

function formatPercent(value: string): string {
  const parsed = Number(value);
  if (!Number.isFinite(parsed)) {
    return '-';
  }
  return `${(parsed * 100).toFixed(1)}%`;
}

function formatDecimal(value: string, digits: number): string {
  const parsed = Number(value);
  if (!Number.isFinite(parsed)) {
    return value;
  }
  return parsed.toFixed(digits);
}

function formatDateTime(value: string | null | undefined): string {
  if (!value) {
    return '-';
  }
  return value.replace('T', ' ').slice(0, 19);
}

function parseOptionalNumber(value: string): number | null {
  if (value.trim() === '') {
    return null;
  }
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : null;
}

function clampNumber(value: string, min: number, max: number): number {
  const parsed = Number(value);
  if (!Number.isFinite(parsed)) {
    return min;
  }
  return Math.min(max, Math.max(min, parsed));
}

function latestDate(values: (string | null)[]): string | null {
  return values.filter((value): value is string => value !== null).sort().at(-1) ?? null;
}

const fallbackFactors: FactorDefinition[] = [
  {
    calculation_method: '直接采用财报指标',
    category: 'profitability',
    code: 'roe',
    description: '衡量股东权益创造利润的能力。',
    latest_factor_date: null,
    latest_report_end_date: null,
    latest_value_count: 0,
    name: '净资产收益率',
    period_type: 'report',
    sort_direction: 'desc',
    source: 'tushare.fina_indicator.roe',
    stock_count: 0,
    unit: '%',
    value_count: 0,
  },
];
