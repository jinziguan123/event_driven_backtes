export type AppView = 'history' | 'create' | 'pools';

export type DrawdownWindow = {
  peak_time: string | null;
  trough_time: string | null;
  recovery_time: string | null;
  max_drawdown: number;
};

export type StrategyOption = {
  name: string;
  path: string;
};

export type StockPoolSummary = {
  pool_id: string;
  name: string;
  description: string;
  symbol_count: number;
  created_at: string;
  updated_at: string;
};

export type StockPoolDetail = StockPoolSummary & {
  symbols: string[];
};

export type StockPoolPayload = {
  name: string;
  description: string;
  symbols: string[];
};

export type StockSymbolOption = {
  symbol: string;
};

export type StockSymbolPage = {
  items: StockSymbolOption[];
  total: number;
  page: number;
  page_size: number;
};

export type BacktestRun = {
  run_id: string;
  name: string;
  strategy_name: string;
  status: string;
  params_json?: string;
  created_at?: string;
  started_at?: string;
  finished_at?: string;
  error_message?: string;
  total_return?: number;
  annual_return?: number;
  sharpe_ratio?: number;
  max_drawdown?: number;
  win_rate?: number;
  trade_count?: number;
  summary?: {
    run_id: string;
    strategy_name: string;
    metrics: Record<string, number>;
    config: Record<string, unknown>;
    max_drawdown_window?: DrawdownWindow;
    profile?: Record<string, unknown>;
  };
};

export type BacktestCreatePayload = {
  name: string;
  strategy_name: string;
  strategy_path?: string;
  pool_id?: string;
  symbols?: string[];
  initial_cash: number;
  start_datetime?: string;
  end_datetime?: string;
  bar_frequency: string;
  max_positions: number;
  adjustment: string;
  match_mode: string;
  benchmark: string;
};

export type SummaryMetric = {
  label: string;
  value: string | number;
};

export type EquityPoint = {
  timestamp: string;
  cash: number;
  market_value: number;
  total_equity: number;
  position_ratio: number;
};

export type BenchmarkPoint = {
  timestamp: string;
  benchmark_price: number;
  benchmark_equity: number;
  benchmark_return: number;
};

export type DrawdownPoint = {
  timestamp: string;
  strategy_drawdown: number;
  benchmark_drawdown?: number;
};

export type TradeRecord = {
  timestamp: string;
  symbol: string;
  side: string;
  quantity: number;
  price: number;
  pnl: number;
  commission?: number;
  stamp_duty?: number;
};

export type DailyTradeRecord = {
  date: string;
  buy_count: number;
  sell_count: number;
  buy_amount: number;
  sell_amount: number;
  realized_pnl: number;
  commission: number;
  stamp_duty: number;
};

export type PositionRecord = {
  timestamp: string;
  symbol: string;
  quantity: number;
  sellable_quantity: number;
  avg_cost: number;
  market_value: number;
  unrealized_pnl: number;
};

export type DailyPositionRecord = {
  date: string;
  position_symbol_count: number;
  total_quantity: number;
  total_market_value: number;
  total_unrealized_pnl: number;
};

export type LogRecord = {
  timestamp: string;
  level: string;
  message: string;
  extra?: Record<string, unknown>;
};

export type BacktestStreamSnapshot = {
  run_id: string;
  status: string;
  detail?: BacktestRun;
  equity: EquityPoint[];
  benchmark: BenchmarkPoint[];
  drawdown: DrawdownPoint[];
  trades: TradeRecord[];
  positions: PositionRecord[];
  logs: LogRecord[];
};

export type BacktestStatusEvent = {
  run_id: string;
  status: string;
  error_message?: string;
};

export type BacktestCompleteEvent = {
  run_id: string;
  status: string;
  detail?: BacktestRun;
  error_message?: string;
};

export type QueryGranularity = 'raw' | 'day';

export type BacktestProfile = {
  run_id: string;
  profile: Record<string, unknown>;
};
