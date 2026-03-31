import { useCallback, useEffect, useMemo, useState, type ReactNode } from 'react';

import {
  buildBacktestStreamUrl,
  cancelBacktest,
  deleteBacktest,
  getBacktest,
  getBacktestProfile,
  getBenchmark,
  getDrawdown,
  getEquity,
  getLogs,
  getPositions,
  getTrades,
} from '../api/client';
import DrawdownChart from '../components/DrawdownChart';
import DrawdownWindowPanel from '../components/DrawdownWindowPanel';
import EquityChart from '../components/EquityChart';
import LogsPanel from '../components/LogsPanel';
import PositionsTable from '../components/PositionsTable';
import StatusBadge from '../components/StatusBadge';
import SummaryCards from '../components/SummaryCards';
import TradesTable from '../components/TradesTable';
import { formatDisplayDateTime } from '../utils/datetimeFormat';
import type {
  BacktestCompleteEvent,
  BacktestRun,
  BacktestStatusEvent,
  BacktestStreamSnapshot,
  BenchmarkPoint,
  DailyPositionRecord,
  DailyTradeRecord,
  DrawdownPoint,
  EquityPoint,
  LogRecord,
  PositionRecord,
  QueryGranularity,
  SummaryMetric,
  TradeRecord,
} from '../types';

type BacktestDetailPageProps = {
  runId: string | null;
  onRunSettled: () => void;
  onRunDeleted: (runId: string) => void;
};

type StreamState = 'idle' | 'connecting' | 'connected' | 'closed' | 'error';

const STREAM_STATE_ZH: Record<StreamState, string> = {
  idle: '空闲',
  connecting: '连接中',
  connected: '已连接',
  closed: '已关闭',
  error: '异常',
};

type QueryPanelProps = {
  title: string;
  open: boolean;
  onToggle: () => void;
  startDate: string;
  endDate: string;
  granularity: QueryGranularity;
  onStartDateChange: (value: string) => void;
  onEndDateChange: (value: string) => void;
  onGranularityChange: (value: QueryGranularity) => void;
  onQuery: () => void;
  loading: boolean;
  error: string;
  children: ReactNode;
};

function QueryPanel({
  title,
  open,
  onToggle,
  startDate,
  endDate,
  granularity,
  onStartDateChange,
  onEndDateChange,
  onGranularityChange,
  onQuery,
  loading,
  error,
  children,
}: QueryPanelProps) {
  return (
    <section className="panel-card query-panel-card">
      <button type="button" className="query-panel-toggle" onClick={onToggle}>
        <div>
          <div className="section-title">{title}</div>
          <div className="chart-caption">默认折叠；展开后先设置条件，再点击查询，支持原始明细与按天聚合。</div>
        </div>
        <span className="toggle-indicator">{open ? '收起' : '展开'}</span>
      </button>
      {open ? (
        <div className="query-panel-body">
          <div className="query-toolbar">
            <label>
              <span>开始日期</span>
              <input type="date" value={startDate} onChange={(event) => onStartDateChange(event.target.value)} />
            </label>
            <label>
              <span>结束日期</span>
              <input type="date" value={endDate} onChange={(event) => onEndDateChange(event.target.value)} />
            </label>
            <label>
              <span>粒度</span>
              <select value={granularity} onChange={(event) => onGranularityChange(event.target.value as QueryGranularity)}>
                <option value="raw">原始明细</option>
                <option value="day">按天聚合</option>
              </select>
            </label>
            <button type="button" onClick={onQuery} disabled={loading}>
              {loading ? '查询中...' : '查询'}
            </button>
          </div>
          {error ? <p className="status-text error">{error}</p> : null}
          {children}
        </div>
      ) : null}
    </section>
  );
}

function formatPercent(value?: number): string {
  if (typeof value !== 'number' || Number.isNaN(value)) {
    return '--';
  }
  return `${(value * 100).toFixed(2)}%`;
}

function formatCurrency(value?: number): string {
  if (typeof value !== 'number' || Number.isNaN(value)) {
    return '--';
  }
  return new Intl.NumberFormat('zh-CN', {
    style: 'currency',
    currency: 'CNY',
    maximumFractionDigits: 2,
  }).format(value);
}

function formatSharpe(value?: number): string {
  if (typeof value !== 'number' || Number.isNaN(value)) {
    return '--';
  }
  return value.toFixed(3);
}

function formatRunPhaseStatus(value: unknown): string {
  if (value == null || value === '') {
    return '--';
  }
  const s = String(value);
  const map: Record<string, string> = {
    SUCCESS: '成功',
    FAILED: '失败',
    RUNNING: '运行中',
    CANCELING: '中断中',
    CANCELED: '已中断',
  };
  return map[s] ?? s;
}

function formatDuration(value: unknown): string {
  if (typeof value !== 'number' || Number.isNaN(value)) {
    return '--';
  }
  return `${value.toFixed(3)}s`;
}

function formatCount(value: unknown): string {
  if (typeof value !== 'number' || Number.isNaN(value)) {
    return '--';
  }
  return String(Math.round(value));
}

function appendUnique<T>(rows: T[], nextItem: T, buildKey: (item: T) => string): T[] {
  const nextKey = buildKey(nextItem);
  if (rows.some((item) => buildKey(item) === nextKey)) {
    return rows;
  }
  return [...rows, nextItem];
}

export default function BacktestDetailPage({ runId, onRunSettled, onRunDeleted }: BacktestDetailPageProps) {
  const [detail, setDetail] = useState<BacktestRun | null>(null);
  const [equity, setEquity] = useState<EquityPoint[]>([]);
  const [benchmark, setBenchmark] = useState<BenchmarkPoint[]>([]);
  const [drawdown, setDrawdown] = useState<DrawdownPoint[]>([]);
  const [logs, setLogs] = useState<LogRecord[]>([]);
  const [liveTrades, setLiveTrades] = useState<TradeRecord[]>([]);
  const [livePositions, setLivePositions] = useState<PositionRecord[]>([]);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const [streamState, setStreamState] = useState<StreamState>('idle');
  const [actionLoading, setActionLoading] = useState<'cancel' | 'delete' | null>(null);
  const [actionMessage, setActionMessage] = useState('');
  const [profile, setProfile] = useState<Record<string, unknown>>({});

  const [tradePanelOpen, setTradePanelOpen] = useState(false);
  const [tradeStartDate, setTradeStartDate] = useState('');
  const [tradeEndDate, setTradeEndDate] = useState('');
  const [tradeGranularity, setTradeGranularity] = useState<QueryGranularity>('raw');
  const [tradeRows, setTradeRows] = useState<TradeRecord[] | DailyTradeRecord[]>([]);
  const [tradeHasQueried, setTradeHasQueried] = useState(false);
  const [tradeLoading, setTradeLoading] = useState(false);
  const [tradeError, setTradeError] = useState('');

  const [positionPanelOpen, setPositionPanelOpen] = useState(false);
  const [positionStartDate, setPositionStartDate] = useState('');
  const [positionEndDate, setPositionEndDate] = useState('');
  const [positionGranularity, setPositionGranularity] = useState<QueryGranularity>('raw');
  const [positionRows, setPositionRows] = useState<PositionRecord[] | DailyPositionRecord[]>([]);
  const [positionHasQueried, setPositionHasQueried] = useState(false);
  const [positionLoading, setPositionLoading] = useState(false);
  const [positionError, setPositionError] = useState('');

  const loadRunData = useCallback(async () => {
    if (!runId) {
      return;
    }
    setLoading(true);
    setError('');

    try {
      const [detailResult, equityResult, benchmarkResult, drawdownResult, logsResult] = await Promise.all([
        getBacktest(runId),
        getEquity(runId),
        getBenchmark(runId),
        getDrawdown(runId),
        getLogs(runId),
      ]);
      const profileResult = await getBacktestProfile(runId).catch(() => null);
      setDetail(detailResult);
      setEquity(equityResult);
      setBenchmark(benchmarkResult);
      setDrawdown(drawdownResult);
      setLogs(logsResult);
      setProfile(profileResult?.profile ?? detailResult.summary?.profile ?? {});
      setLiveTrades([]);
      setLivePositions([]);
      setTradeRows([]);
      setTradeHasQueried(false);
      setPositionRows([]);
      setPositionHasQueried(false);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : '加载详情失败');
    } finally {
      setLoading(false);
    }
  }, [runId]);

  useEffect(() => {
    if (!runId) {
      setDetail(null);
      setEquity([]);
      setBenchmark([]);
      setDrawdown([]);
      setLogs([]);
      setLiveTrades([]);
      setLivePositions([]);
      setTradeRows([]);
      setTradeHasQueried(false);
      setPositionRows([]);
      setPositionHasQueried(false);
      setError('');
      setLoading(false);
      setStreamState('idle');
      setActionLoading(null);
      setActionMessage('');
      setProfile({});
      return;
    }

    void loadRunData();
  }, [runId, loadRunData]);

  useEffect(() => {
    if (!runId || !detail || (detail.status !== 'RUNNING' && detail.status !== 'CANCELING')) {
      if (detail && detail.status !== 'RUNNING' && detail.status !== 'CANCELING') {
        setStreamState('closed');
      }
      return;
    }

    const source = new EventSource(buildBacktestStreamUrl(runId));
    setStreamState('connecting');

    source.onopen = () => {
      setStreamState('connected');
    };

    source.addEventListener('snapshot', (event) => {
      const payload = JSON.parse((event as MessageEvent<string>).data) as BacktestStreamSnapshot;
      setDetail((current) => payload.detail ?? (current ? { ...current, status: payload.status } : current));
      setEquity(payload.equity ?? []);
      setBenchmark(payload.benchmark ?? []);
      setDrawdown(payload.drawdown ?? []);
      setLogs(payload.logs ?? []);
      setLiveTrades(payload.trades ?? []);
      setLivePositions(payload.positions ?? []);
      setError('');
    });

    source.addEventListener('status', (event) => {
      const payload = JSON.parse((event as MessageEvent<string>).data) as BacktestStatusEvent;
      setDetail((current) => (current ? { ...current, status: payload.status, error_message: payload.error_message } : current));
      if (payload.status === 'CANCELED') {
        setActionMessage('回测已中断');
      }
    });

    source.addEventListener('log', (event) => {
      const payload = JSON.parse((event as MessageEvent<string>).data) as LogRecord;
      setLogs((current) => appendUnique(current, payload, (item) => `${item.timestamp}-${item.level}-${item.message}`));
    });

    source.addEventListener('equity', (event) => {
      const payload = JSON.parse((event as MessageEvent<string>).data) as EquityPoint;
      setEquity((current) => appendUnique(current, payload, (item) => item.timestamp));
    });

    source.addEventListener('trade', (event) => {
      const payload = JSON.parse((event as MessageEvent<string>).data) as TradeRecord;
      setLiveTrades((current) => appendUnique(current, payload, (item) => `${item.timestamp}-${item.symbol}-${item.side}-${item.quantity}-${item.price}`));
      if (tradePanelOpen && tradeHasQueried && tradeGranularity === 'raw' && !tradeStartDate && !tradeEndDate) {
        setTradeRows((current) => appendUnique(current as TradeRecord[], payload, (item) => `${item.timestamp}-${item.symbol}-${item.side}-${item.quantity}-${item.price}`));
      }
    });

    source.addEventListener('position', (event) => {
      const payload = JSON.parse((event as MessageEvent<string>).data) as PositionRecord;
      setLivePositions((current) => appendUnique(current, payload, (item) => `${item.timestamp}-${item.symbol}-${item.quantity}-${item.market_value}`));
      if (positionPanelOpen && positionHasQueried && positionGranularity === 'raw' && !positionStartDate && !positionEndDate) {
        setPositionRows((current) => appendUnique(current as PositionRecord[], payload, (item) => `${item.timestamp}-${item.symbol}-${item.quantity}-${item.market_value}`));
      }
    });

    source.addEventListener('complete', (event) => {
      const payload = JSON.parse((event as MessageEvent<string>).data) as BacktestCompleteEvent;
      setDetail((current) => (current ? { ...current, status: payload.status, error_message: payload.error_message } : current));
      setStreamState('closed');
      source.close();
      void loadRunData().finally(onRunSettled);
    });

    source.onerror = () => {
      setStreamState('error');
    };

    return () => {
      source.close();
      setStreamState('closed');
    };
  }, [
    detail?.status,
    loadRunData,
    onRunSettled,
    positionEndDate,
    positionGranularity,
    positionHasQueried,
    positionPanelOpen,
    positionStartDate,
    runId,
    tradeEndDate,
    tradeGranularity,
    tradeHasQueried,
    tradePanelOpen,
    tradeStartDate,
  ]);

  const metrics = useMemo<SummaryMetric[]>(() => {
    if (!detail) {
      return [];
    }
    const summaryMetrics = detail.summary?.metrics ?? {};
    return [
      { label: '总收益', value: formatPercent(detail.total_return ?? summaryMetrics.total_return) },
      { label: '年化收益', value: formatPercent(detail.annual_return ?? summaryMetrics.annual_return) },
      { label: '夏普比率', value: formatSharpe(detail.sharpe_ratio ?? summaryMetrics.sharpe_ratio) },
      { label: '最大回撤', value: formatPercent(detail.max_drawdown ?? summaryMetrics.max_drawdown) },
      { label: '胜率', value: formatPercent(detail.win_rate ?? summaryMetrics.win_rate) },
      { label: '交易次数', value: detail.trade_count ?? summaryMetrics.trade_count ?? 0 },
    ];
  }, [detail]);

  const mergedProfile = useMemo(() => {
    const summaryProfile = detail?.summary?.profile;
    if (summaryProfile && Object.keys(summaryProfile).length > 0) {
      return summaryProfile;
    }
    return profile;
  }, [detail?.summary?.profile, profile]);

  const latestEquity = equity.length > 0 ? equity[equity.length - 1] : undefined;
  const isRunning = detail?.status === 'RUNNING' || detail?.status === 'CANCELING';
  const canCancel = detail?.status === 'RUNNING' || detail?.status === 'CANCELING';
  const canDelete = Boolean(detail && !canCancel);

  const handleCancelRun = useCallback(async () => {
    if (!runId) {
      return;
    }
    setActionLoading('cancel');
    setError('');
    setActionMessage('');
    try {
      const result = await cancelBacktest(runId);
      setDetail((current) => (current ? { ...current, status: result.status } : current));
      setActionMessage(result.message || (result.accepted ? '已提交中断请求' : '当前状态不可中断'));
      onRunSettled();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : '提交中断请求失败');
    } finally {
      setActionLoading(null);
    }
  }, [onRunSettled, runId]);

  const handleDeleteRun = useCallback(async () => {
    if (!runId) {
      return;
    }
    if (!window.confirm('确认删除这条回测记录吗？删除后无法恢复。')) {
      return;
    }

    setActionLoading('delete');
    setError('');
    setActionMessage('');
    try {
      await deleteBacktest(runId);
      setActionMessage('回测记录已删除');
      onRunDeleted(runId);
      onRunSettled();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : '删除回测记录失败');
    } finally {
      setActionLoading(null);
    }
  }, [onRunDeleted, onRunSettled, runId]);

  const executeTradeQuery = useCallback(async () => {
    if (!runId) {
      return;
    }
    setTradeHasQueried(true);
    setTradeLoading(true);
    setTradeError('');
    try {
      if (isRunning && tradeGranularity === 'raw' && !tradeStartDate && !tradeEndDate) {
        setTradeRows(liveTrades);
      } else {
        const result = await getTrades(runId, {
          startDate: tradeStartDate || undefined,
          endDate: tradeEndDate || undefined,
          granularity: tradeGranularity,
        });
        setTradeRows(result);
      }
    } catch (reason) {
      setTradeError(reason instanceof Error ? reason.message : '查询交易记录失败');
    } finally {
      setTradeLoading(false);
    }
  }, [isRunning, liveTrades, runId, tradeEndDate, tradeGranularity, tradeStartDate]);

  const executePositionQuery = useCallback(async () => {
    if (!runId) {
      return;
    }
    setPositionHasQueried(true);
    setPositionLoading(true);
    setPositionError('');
    try {
      if (isRunning && positionGranularity === 'raw' && !positionStartDate && !positionEndDate) {
        setPositionRows(livePositions);
      } else {
        const result = await getPositions(runId, {
          startDate: positionStartDate || undefined,
          endDate: positionEndDate || undefined,
          granularity: positionGranularity,
        });
        setPositionRows(result);
      }
    } catch (reason) {
      setPositionError(reason instanceof Error ? reason.message : '查询持仓快照失败');
    } finally {
      setPositionLoading(false);
    }
  }, [isRunning, livePositions, positionEndDate, positionGranularity, positionStartDate, runId]);

  function toggleTradePanel() {
    setTradePanelOpen((current) => !current);
  }

  function togglePositionPanel() {
    setPositionPanelOpen((current) => !current);
  }

  function handleTradeStartDateChange(value: string) {
    setTradeStartDate(value);
    setTradeHasQueried(false);
    setTradeRows([]);
  }

  function handleTradeEndDateChange(value: string) {
    setTradeEndDate(value);
    setTradeHasQueried(false);
    setTradeRows([]);
  }

  function handleTradeGranularityChange(value: QueryGranularity) {
    setTradeGranularity(value);
    setTradeHasQueried(false);
    setTradeRows([]);
  }

  function handlePositionStartDateChange(value: string) {
    setPositionStartDate(value);
    setPositionHasQueried(false);
    setPositionRows([]);
  }

  function handlePositionEndDateChange(value: string) {
    setPositionEndDate(value);
    setPositionHasQueried(false);
    setPositionRows([]);
  }

  function handlePositionGranularityChange(value: QueryGranularity) {
    setPositionGranularity(value);
    setPositionHasQueried(false);
    setPositionRows([]);
  }

  if (!runId) {
    return (
      <section className="panel-card empty-detail-card compact-empty">
        <div className="panel-kicker">History Detail</div>
        <h2 className="panel-heading">请选择一条历史回测</h2>
        <p className="panel-subtitle">创建任务后会自动跳到这里；交易记录和持仓快照现在默认折叠，只有在你主动查询时才加载。</p>
      </section>
    );
  }

  if (loading && !detail) {
    return <section className="panel-card">正在加载回测详情...</section>;
  }

  if (error && !detail) {
    return <section className="panel-card error">{error}</section>;
  }

  return (
    <div className="detail-stack compact-gap">
      <section className="panel-card hero-card detail-hero compact-hero">
        <div className="hero-main compact-main">
          <div>
            <div className="panel-kicker">Run Detail</div>
            <div className="hero-title-row">
              <h2 className="hero-title">{detail?.name || runId}</h2>
              {detail ? <StatusBadge status={detail.status} /> : null}
              <span className={`stream-badge ${streamState}`}>
                {isRunning ? `实时同步：${STREAM_STATE_ZH[streamState]}` : '已持久化结果'}
              </span>
            </div>
            <p className="panel-subtitle">{detail?.strategy_name || '未指定策略'} ｜ Run ID：{runId}</p>
          </div>
          <div className="hero-meta-grid compact-meta-grid">
            <div>
              <span className="hero-meta-label">开始时间</span>
              <strong className="hero-meta-value">{formatDisplayDateTime(detail?.started_at || detail?.created_at)}</strong>
            </div>
            <div>
              <span className="hero-meta-label">结束时间</span>
              <strong className="hero-meta-value">{formatDisplayDateTime(detail?.finished_at)}</strong>
            </div>
            <div>
              <span className="hero-meta-label">当前权益</span>
              <strong className="hero-meta-value">{formatCurrency(latestEquity?.total_equity)}</strong>
            </div>
          </div>
        </div>
        <div className="button-row">
          {canCancel ? (
            <button type="button" className="secondary-button" onClick={() => void handleCancelRun()} disabled={actionLoading !== null}>
              {actionLoading === 'cancel' ? '处理中...' : '中断回测'}
            </button>
          ) : null}
          {canDelete ? (
            <button type="button" className="secondary-button danger-button" onClick={() => void handleDeleteRun()} disabled={actionLoading !== null}>
              {actionLoading === 'delete' ? '删除中...' : '删除回测'}
            </button>
          ) : null}
        </div>
        {error ? <p className="status-text error">{error}</p> : null}
        {actionMessage ? <p className="status-text">{actionMessage}</p> : null}
        {detail?.error_message ? <p className="status-text error">{detail.error_message}</p> : null}
      </section>

      <section className="panel-card compact-card">
        <SummaryCards metrics={metrics} />
      </section>

      <section className="panel-card compact-card">
        <div className="section-title">性能画像</div>
        <div className="chart-caption">用于定位慢点：优先看数据加载、引擎运行、持久化和总耗时。</div>
        <div className="profile-grid">
          <div className="profile-card">
            <div className="profile-label">数据加载</div>
            <div className="profile-value">{formatDuration(mergedProfile.data_load_seconds)}</div>
          </div>
          <div className="profile-card">
            <div className="profile-label">引擎运行</div>
            <div className="profile-value">{formatDuration(mergedProfile.engine_run_seconds)}</div>
          </div>
          <div className="profile-card">
            <div className="profile-label">持久化</div>
            <div className="profile-value">{formatDuration(mergedProfile.persist_seconds)}</div>
          </div>
          <div className="profile-card accent">
            <div className="profile-label">总耗时</div>
            <div className="profile-value">{formatDuration(mergedProfile.total_seconds)}</div>
          </div>
          <div className="profile-card">
            <div className="profile-label">股票数</div>
            <div className="profile-value">{formatCount(mergedProfile.symbol_count)}</div>
          </div>
          <div className="profile-card">
            <div className="profile-label">权益点</div>
            <div className="profile-value">{formatCount(mergedProfile.equity_points)}</div>
          </div>
          <div className="profile-card">
            <div className="profile-label">成交笔数</div>
            <div className="profile-value">{formatCount(mergedProfile.trade_count_runtime)}</div>
          </div>
          <div className="profile-card">
            <div className="profile-label">阶段状态</div>
            <div className="profile-value">{formatRunPhaseStatus(mergedProfile.final_status)}</div>
          </div>
        </div>
      </section>

      {isRunning ? (
        <section className="panel-card live-strip compact-live-strip">
          <div className="live-card">
            <span className="live-label">实时权益点</span>
            <strong className="live-value">{equity.length}</strong>
          </div>
          <div className="live-card">
            <span className="live-label">实时成交笔数</span>
            <strong className="live-value">{liveTrades.length}</strong>
          </div>
          <div className="live-card">
            <span className="live-label">实时日志条数</span>
            <strong className="live-value">{logs.length}</strong>
          </div>
          <div className="live-card">
            <span className="live-label">流连接状态</span>
            <strong className="live-value">{STREAM_STATE_ZH[streamState]}</strong>
          </div>
        </section>
      ) : null}

      <EquityChart equity={equity} benchmark={benchmark} drawdownWindow={detail?.summary?.max_drawdown_window} />
      <DrawdownWindowPanel window={detail?.summary?.max_drawdown_window} />
      <DrawdownChart rows={drawdown} drawdownWindow={detail?.summary?.max_drawdown_window} />
      <LogsPanel rows={logs} />

      <QueryPanel
        title="交易记录查询"
        open={tradePanelOpen}
        onToggle={toggleTradePanel}
        startDate={tradeStartDate}
        endDate={tradeEndDate}
        granularity={tradeGranularity}
        onStartDateChange={handleTradeStartDateChange}
        onEndDateChange={handleTradeEndDateChange}
        onGranularityChange={handleTradeGranularityChange}
        onQuery={() => void executeTradeQuery()}
        loading={tradeLoading}
        error={tradeError}
      >
        {tradeHasQueried ? (
          <TradesTable rows={tradeRows} granularity={tradeGranularity} exportBasename={runId} />
        ) : (
          <div className="query-empty-hint">设置好条件后点击“查询”，再加载交易记录。</div>
        )}
      </QueryPanel>

      <QueryPanel
        title="持仓快照查询"
        open={positionPanelOpen}
        onToggle={togglePositionPanel}
        startDate={positionStartDate}
        endDate={positionEndDate}
        granularity={positionGranularity}
        onStartDateChange={handlePositionStartDateChange}
        onEndDateChange={handlePositionEndDateChange}
        onGranularityChange={handlePositionGranularityChange}
        onQuery={() => void executePositionQuery()}
        loading={positionLoading}
        error={positionError}
      >
        {positionHasQueried ? (
          <PositionsTable rows={positionRows} granularity={positionGranularity} exportBasename={runId} />
        ) : (
          <div className="query-empty-hint">设置好条件后点击“查询”，再加载持仓快照。</div>
        )}
      </QueryPanel>
    </div>
  );
}
