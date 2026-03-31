import { useEffect, useMemo, useState, type ChangeEvent, type FormEvent } from 'react';

import { createBacktest, getStockPool, listStockPools, listStrategies } from '../api/client';
import type { BacktestCreatePayload, StockPoolDetail, StockPoolSummary, StrategyOption } from '../types';

type BacktestCreatePageProps = {
  onCreated: (runId: string) => void;
  onOpenStockPools: () => void;
};

const defaultPayload: BacktestCreatePayload = {
  name: '事件驱动回测示例',
  strategy_name: '',
  strategy_path: '',
  pool_id: '',
  initial_cash: 1_000_000,
  start_datetime: '',
  end_datetime: '',
  bar_frequency: '1m',
  max_positions: 5,
  adjustment: 'qfq',
  match_mode: 'next_open',
  benchmark: '000300.SH',
};

const frequencyOptions = ['1m', '5m', '15m', '30m', '60m', '1d'];
const matchModeOptions = ['close', 'next_open', 'limit'];
const adjustmentOptions = ['qfq', 'none'];

function pickDefaultStrategy(strategies: StrategyOption[]): StrategyOption | undefined {
  return strategies.find((item) => item.name === 'minute_sma_5_20') ?? strategies[0];
}

export default function BacktestCreatePage({ onCreated, onOpenStockPools }: BacktestCreatePageProps) {
  const [payload, setPayload] = useState(defaultPayload);
  const [strategies, setStrategies] = useState<StrategyOption[]>([]);
  const [stockPools, setStockPools] = useState<StockPoolSummary[]>([]);
  const [selectedPool, setSelectedPool] = useState<StockPoolDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [pageError, setPageError] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [message, setMessage] = useState('');

  const selectedPoolSummary = useMemo(
    () => stockPools.find((item) => item.pool_id === payload.pool_id) ?? null,
    [payload.pool_id, stockPools],
  );

  useEffect(() => {
    let canceled = false;
    setLoading(true);
    setPageError('');

    Promise.all([listStrategies(), listStockPools()])
      .then(async ([strategyItems, poolItems]) => {
        if (canceled) {
          return;
        }
        setStrategies(strategyItems);
        setStockPools(poolItems);

        const selectedStrategy = pickDefaultStrategy(strategyItems);
        const firstPool = poolItems[0];
        setPayload((current) => ({
          ...current,
          strategy_name: selectedStrategy?.name ?? '',
          strategy_path: selectedStrategy?.path ?? '',
          pool_id: current.pool_id || firstPool?.pool_id || '',
        }));

        if (firstPool) {
          const detail = await getStockPool(firstPool.pool_id);
          if (!canceled) {
            setSelectedPool(detail);
          }
        }
      })
      .catch((error) => {
        if (!canceled) {
          setPageError(error instanceof Error ? error.message : '加载创建页数据失败');
        }
      })
      .finally(() => {
        if (!canceled) {
          setLoading(false);
        }
      });

    return () => {
      canceled = true;
    };
  }, []);

  async function handlePoolChange(event: ChangeEvent<HTMLSelectElement>) {
    const poolId = event.target.value;
    setPayload((current) => ({ ...current, pool_id: poolId }));
    if (!poolId) {
      setSelectedPool(null);
      return;
    }
    try {
      const detail = await getStockPool(poolId);
      setSelectedPool(detail);
    } catch (error) {
      setPageError(error instanceof Error ? error.message : '加载股票池详情失败');
    }
  }

  function handleStrategyChange(event: ChangeEvent<HTMLSelectElement>) {
    const nextPath = event.target.value;
    const selected = strategies.find((item) => item.path === nextPath);
    if (!selected) {
      return;
    }
    setPayload((current) => ({
      ...current,
      strategy_name: selected.name,
      strategy_path: selected.path,
    }));
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!payload.pool_id) {
      setPageError('请先选择股票池');
      return;
    }
    setSubmitting(true);
    setMessage('正在提交回测任务，创建后将自动跳转到历史详情页...');

    try {
      const requestPayload = {
        ...payload,
        symbols: undefined,
        start_datetime: payload.start_datetime || undefined,
        end_datetime: payload.end_datetime || undefined,
      };
      const result = await createBacktest(requestPayload);
      setMessage(`回测任务已创建：${result.run_id}`);
      onCreated(result.run_id);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : '创建回测失败');
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="detail-stack compact-gap">
      <section className="panel-card hero-card create-hero compact-hero">
        <div>
          <div className="panel-kicker">Create</div>
          <h2 className="panel-heading">新建回测</h2>
          <p className="panel-subtitle">时间区使用选择器，股票池从独立管理页复用，表单只保留回测必需项。</p>
        </div>
        <div className="hero-inline-stats two-column">
          <div className="hero-inline-stat">
            <span className="hero-inline-label">策略数量</span>
            <strong className="hero-inline-value">{strategies.length}</strong>
          </div>
          <div className="hero-inline-stat">
            <span className="hero-inline-label">股票池数量</span>
            <strong className="hero-inline-value">{stockPools.length}</strong>
          </div>
        </div>
      </section>

      <section className="panel-card">
        <form className="create-form compact-form" onSubmit={handleSubmit}>
          <div className="form-section compact-section">
            <div className="form-section-header compact-header">
              <h3>策略与股票池</h3>
              <p>策略列表来自后端策略目录；股票池来自独立管理模块。</p>
            </div>
            <div className="form-grid">
              <label>
                <span>回测名称</span>
                <input value={payload.name} onChange={(event) => setPayload((current) => ({ ...current, name: event.target.value }))} />
              </label>
              <label>
                <span>策略选择</span>
                <select value={payload.strategy_path ?? ''} onChange={handleStrategyChange} disabled={loading || strategies.length === 0}>
                  <option value="">{loading ? '正在加载策略...' : '请选择策略'}</option>
                  {strategies.map((item) => (
                    <option key={item.path} value={item.path}>
                      {item.name}
                    </option>
                  ))}
                </select>
              </label>
              <label>
                <span>股票池</span>
                <select value={payload.pool_id ?? ''} onChange={(event) => void handlePoolChange(event)} disabled={loading || stockPools.length === 0}>
                  <option value="">{loading ? '正在加载股票池...' : '请选择股票池'}</option>
                  {stockPools.map((pool) => (
                    <option key={pool.pool_id} value={pool.pool_id}>
                      {pool.name}（{pool.symbol_count}）
                    </option>
                  ))}
                </select>
              </label>
              <label>
                <span>股票池管理</span>
                <button type="button" className="secondary-button input-button" onClick={onOpenStockPools}>
                  打开股票池管理
                </button>
              </label>
            </div>
            <div className="pool-preview-card">
              <div className="pool-preview-header">
                <div>
                  <div className="pool-preview-title">{selectedPoolSummary?.name ?? '未选择股票池'}</div>
                  <div className="pool-preview-subtitle">{selectedPool?.description || '在股票池管理页可维护说明与成分股。'}</div>
                </div>
                <div className="pool-count-pill">{selectedPool?.symbols.length ?? 0} 只股票</div>
              </div>
              <div className="pool-symbol-preview">{selectedPool?.symbols.slice(0, 10).join('，') || '暂无股票预览'}</div>
            </div>
          </div>

          <div className="form-section compact-section">
            <div className="form-section-header compact-header">
              <h3>时间与撮合</h3>
              <p>统一使用选择器与下拉框，减少手输错误。</p>
            </div>
            <div className="form-grid">
              <label>
                <span>开始时间</span>
                <input type="datetime-local" value={payload.start_datetime} onChange={(event) => setPayload((current) => ({ ...current, start_datetime: event.target.value }))} />
              </label>
              <label>
                <span>结束时间</span>
                <input type="datetime-local" value={payload.end_datetime} onChange={(event) => setPayload((current) => ({ ...current, end_datetime: event.target.value }))} />
              </label>
              <label>
                <span>回测周期</span>
                <select value={payload.bar_frequency} onChange={(event) => setPayload((current) => ({ ...current, bar_frequency: event.target.value }))}>
                  {frequencyOptions.map((item) => (
                    <option key={item} value={item}>
                      {item}
                    </option>
                  ))}
                </select>
              </label>
              <label>
                <span>成交模式</span>
                <select value={payload.match_mode} onChange={(event) => setPayload((current) => ({ ...current, match_mode: event.target.value }))}>
                  {matchModeOptions.map((item) => (
                    <option key={item} value={item}>
                      {item}
                    </option>
                  ))}
                </select>
              </label>
              <label>
                <span>复权方式</span>
                <select value={payload.adjustment} onChange={(event) => setPayload((current) => ({ ...current, adjustment: event.target.value }))}>
                  {adjustmentOptions.map((item) => (
                    <option key={item} value={item}>
                      {item}
                    </option>
                  ))}
                </select>
              </label>
              <label>
                <span>基准代码</span>
                <input value={payload.benchmark} onChange={(event) => setPayload((current) => ({ ...current, benchmark: event.target.value }))} placeholder="000300.SH" />
              </label>
            </div>
          </div>

          <div className="form-section compact-section">
            <div className="form-section-header compact-header">
              <h3>资金与风控</h3>
              <p>保留常用参数，避免表单过长。</p>
            </div>
            <div className="form-grid compact-grid">
              <label>
                <span>初始资金</span>
                <input type="number" value={payload.initial_cash} onChange={(event) => setPayload((current) => ({ ...current, initial_cash: Number(event.target.value) || 0 }))} />
              </label>
              <label>
                <span>最大持仓</span>
                <input type="number" value={payload.max_positions} onChange={(event) => setPayload((current) => ({ ...current, max_positions: Number(event.target.value) || 1 }))} />
              </label>
            </div>
          </div>

          <div className="form-actions between">
            <div>
              {pageError ? <p className="status-text error">{pageError}</p> : null}
              {message ? <p className="status-text">{message}</p> : null}
            </div>
            <button type="submit" disabled={submitting || loading || !payload.pool_id || !payload.strategy_path}>
              {submitting ? '创建中...' : '开始回测'}
            </button>
          </div>
        </form>
      </section>
    </div>
  );
}
