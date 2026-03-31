import type {
  BacktestCreatePayload,
  BacktestProfile,
  BacktestRun,
  BenchmarkPoint,
  DailyPositionRecord,
  DailyTradeRecord,
  DrawdownPoint,
  EquityPoint,
  LogRecord,
  PositionRecord,
  QueryGranularity,
  StockSymbolPage,
  StockSymbolOption,
  StockPoolDetail,
  StockPoolPayload,
  StockPoolSummary,
  StrategyOption,
  TradeRecord,
} from '../types';

const API_BASE = '/api';

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    headers: {
      'Content-Type': 'application/json',
    },
    ...init,
  });

  if (!response.ok) {
    let message = `请求失败: ${response.status}`;
    try {
      const payload = (await response.json()) as { detail?: string };
      if (payload?.detail) {
        message = payload.detail;
      }
    } catch (error) {
      void error;
    }
    throw new Error(message);
  }

  if (response.status === 204) {
    return undefined as T;
  }
  return response.json() as Promise<T>;
}

function buildQuery(params: Record<string, string | undefined>): string {
  const searchParams = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value) {
      searchParams.set(key, value);
    }
  }
  const query = searchParams.toString();
  return query ? `?${query}` : '';
}

export function buildBacktestStreamUrl(runId: string): string {
  return `${API_BASE}/backtests/${runId}/stream`;
}

export function listStrategies(): Promise<StrategyOption[]> {
  return request<StrategyOption[]>('/strategies');
}

export function listStockPools(): Promise<StockPoolSummary[]> {
  return request<StockPoolSummary[]>('/stock-pools');
}

export function listStocks(keyword?: string, limit = 200): Promise<StockSymbolOption[]> {
  const query = buildQuery({
    keyword,
    limit: String(limit),
  });
  return request<StockSymbolOption[]>(`/stocks${query}`);
}

export function listStocksPage(options?: { keyword?: string; page?: number; pageSize?: number }): Promise<StockSymbolPage> {
  const query = buildQuery({
    keyword: options?.keyword,
    page: String(options?.page ?? 1),
    page_size: String(options?.pageSize ?? 100),
  });
  return request<StockSymbolPage>(`/stocks/page${query}`);
}

export function getStockPool(poolId: string): Promise<StockPoolDetail> {
  return request<StockPoolDetail>(`/stock-pools/${poolId}`);
}

export function createStockPool(payload: StockPoolPayload): Promise<StockPoolDetail> {
  return request<StockPoolDetail>('/stock-pools', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export function updateStockPool(poolId: string, payload: StockPoolPayload): Promise<StockPoolDetail> {
  return request<StockPoolDetail>(`/stock-pools/${poolId}`, {
    method: 'PUT',
    body: JSON.stringify(payload),
  });
}

export function deleteStockPool(poolId: string): Promise<{ pool_id: string; deleted: boolean }> {
  return request<{ pool_id: string; deleted: boolean }>(`/stock-pools/${poolId}`, {
    method: 'DELETE',
  });
}

export function listBacktests(): Promise<BacktestRun[]> {
  return request<BacktestRun[]>('/backtests');
}

export function cancelBacktest(runId: string): Promise<{ run_id: string; status: string; accepted: boolean; message: string }> {
  return request<{ run_id: string; status: string; accepted: boolean; message: string }>(`/backtests/${runId}/cancel`, {
    method: 'POST',
  });
}

export function deleteBacktest(runId: string): Promise<{ run_id: string; deleted: boolean; message?: string }> {
  return request<{ run_id: string; deleted: boolean; message?: string }>(`/backtests/${runId}`, {
    method: 'DELETE',
  });
}

export function getBacktest(runId: string): Promise<BacktestRun> {
  return request<BacktestRun>(`/backtests/${runId}`);
}

export function getBacktestProfile(runId: string): Promise<BacktestProfile> {
  return request<BacktestProfile>(`/backtests/${runId}/profile`);
}

export function getEquity(runId: string): Promise<EquityPoint[]> {
  return request<EquityPoint[]>(`/backtests/${runId}/equity`);
}

export function getBenchmark(runId: string): Promise<BenchmarkPoint[]> {
  return request<BenchmarkPoint[]>(`/backtests/${runId}/benchmark`);
}

export function getDrawdown(runId: string): Promise<DrawdownPoint[]> {
  return request<DrawdownPoint[]>(`/backtests/${runId}/drawdown`);
}

export function getTrades(
  runId: string,
  options?: { startDate?: string; endDate?: string; granularity?: QueryGranularity },
): Promise<TradeRecord[] | DailyTradeRecord[]> {
  const query = buildQuery({
    start_date: options?.startDate,
    end_date: options?.endDate,
    granularity: options?.granularity,
  });
  return request<TradeRecord[] | DailyTradeRecord[]>(`/backtests/${runId}/trades${query}`);
}

export function getPositions(
  runId: string,
  options?: { startDate?: string; endDate?: string; granularity?: QueryGranularity },
): Promise<PositionRecord[] | DailyPositionRecord[]> {
  const query = buildQuery({
    start_date: options?.startDate,
    end_date: options?.endDate,
    granularity: options?.granularity,
  });
  return request<PositionRecord[] | DailyPositionRecord[]>(`/backtests/${runId}/positions${query}`);
}

export function getLogs(runId: string): Promise<LogRecord[]> {
  return request<LogRecord[]>(`/backtests/${runId}/logs`);
}

export function createBacktest(payload: BacktestCreatePayload): Promise<{ run_id: string; status: string }> {
  return request<{ run_id: string; status: string }>('/backtests', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}
