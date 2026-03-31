import { useMemo, useState } from 'react';

import type { DailyPositionRecord, PositionRecord, QueryGranularity } from '../types';
import { downloadExcel } from '../utils/excelExport';
import { formatDisplayDateTime, normalizeTimestampKey } from '../utils/datetimeFormat';
import RecordCurveChart, { type RecordCurvePoint } from './RecordCurveChart';

type PositionsTableProps = {
  rows: PositionRecord[] | DailyPositionRecord[];
  granularity: QueryGranularity;
  exportBasename?: string;
};

function formatNumber(value: number): string {
  return Number.isFinite(value) ? value.toFixed(2) : '--';
}

function toExcelRows(rows: PositionRecord[] | DailyPositionRecord[], granularity: QueryGranularity): Record<string, unknown>[] {
  if (granularity === 'day') {
    const dailyRows = rows as DailyPositionRecord[];
    return dailyRows.map((row) => ({
      日期: formatDisplayDateTime(row.date),
      持仓股票数: row.position_symbol_count,
      总持仓量: row.total_quantity,
      总市值: row.total_market_value,
      总浮盈亏: row.total_unrealized_pnl,
    }));
  }
  const rawRows = rows as PositionRecord[];
  return rawRows.map((row) => ({
    时间: formatDisplayDateTime(row.timestamp),
    股票: row.symbol,
    持仓: row.quantity,
    可卖: row.sellable_quantity,
    成本: row.avg_cost,
    市值: row.market_value,
    浮盈亏: row.unrealized_pnl,
  }));
}

function buildCurvePoints(rows: PositionRecord[] | DailyPositionRecord[], granularity: QueryGranularity): RecordCurvePoint[] {
  if (granularity === 'day') {
    const dailyRows = [...(rows as DailyPositionRecord[])].sort((a, b) => a.date.localeCompare(b.date));
    return dailyRows.map((row) => ({ label: row.date, value: row.total_market_value }));
  }
  const rawRows = rows as PositionRecord[];
  const byTs = new Map<string, { sortKey: string; total: number }>();
  for (const r of rawRows) {
    const sortKey = normalizeTimestampKey(r.timestamp);
    const prev = byTs.get(sortKey);
    const add = Number(r.market_value) || 0;
    if (prev) {
      prev.total += add;
    } else {
      byTs.set(sortKey, { sortKey, total: add });
    }
  }
  return [...byTs.values()]
    .sort((a, b) => a.sortKey.localeCompare(b.sortKey))
    .map((item) => ({ label: item.sortKey, value: item.total }));
}

export default function PositionsTable({ rows, granularity, exportBasename = 'positions' }: PositionsTableProps) {
  const [showCurve, setShowCurve] = useState(false);
  const curvePoints = useMemo(() => buildCurvePoints(rows, granularity), [rows, granularity]);

  const toolbar = (
    <div className="button-row table-tool-row">
      <button
        type="button"
        className="secondary-button"
        disabled={rows.length === 0}
        onClick={() => downloadExcel(toExcelRows(rows, granularity), '持仓快照', `${exportBasename}-持仓快照`)}
      >
        导出 Excel
      </button>
      <button type="button" className="secondary-button" disabled={rows.length === 0} onClick={() => setShowCurve((v) => !v)}>
        {showCurve ? '隐藏曲线' : '生成曲线'}
      </button>
    </div>
  );

  if (granularity === 'day') {
    const dailyRows = rows as DailyPositionRecord[];
    return (
      <section className="table-card compact-card">
        <header className="section-title">持仓快照（日聚合）</header>
        {toolbar}
        {showCurve ? <RecordCurveChart title="日末总市值" subtitle="按日聚合后的合计市值" points={curvePoints} /> : null}
        <table className="data-table">
          <thead>
            <tr>
              <th>日期</th>
              <th>持仓股票数</th>
              <th>总持仓量</th>
              <th>总市值</th>
              <th>总浮盈亏</th>
            </tr>
          </thead>
          <tbody>
            {dailyRows.length > 0 ? (
              dailyRows.map((row) => (
                <tr key={row.date}>
                  <td>{formatDisplayDateTime(row.date)}</td>
                  <td>{row.position_symbol_count}</td>
                  <td>{row.total_quantity}</td>
                  <td>{formatNumber(row.total_market_value)}</td>
                  <td>{formatNumber(row.total_unrealized_pnl)}</td>
                </tr>
              ))
            ) : (
              <tr>
                <td colSpan={5} className="empty-cell">
                  当前条件下暂无持仓聚合数据
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </section>
    );
  }

  const rawRows = rows as PositionRecord[];
  return (
    <section className="table-card compact-card">
      <header className="section-title">持仓快照</header>
      {toolbar}
      {showCurve ? (
        <RecordCurveChart title="全市场合计市值" subtitle="按快照时间聚合（同一时刻多标的市值相加）" points={curvePoints} />
      ) : null}
      <table className="data-table">
        <thead>
          <tr>
            <th>时间</th>
            <th>股票</th>
            <th>持仓</th>
            <th>可卖</th>
            <th>成本</th>
            <th>市值</th>
            <th>浮盈亏</th>
          </tr>
        </thead>
        <tbody>
          {rawRows.length > 0 ? (
            rawRows
              .slice(-50)
              .reverse()
              .map((row, index) => (
                <tr key={`${row.timestamp}-${row.symbol}-${index}`}>
                  <td>{formatDisplayDateTime(row.timestamp)}</td>
                  <td>{row.symbol}</td>
                  <td>{row.quantity}</td>
                  <td>{row.sellable_quantity}</td>
                  <td>{row.avg_cost}</td>
                  <td>{row.market_value}</td>
                  <td>{row.unrealized_pnl}</td>
                </tr>
              ))
          ) : (
            <tr>
              <td colSpan={7} className="empty-cell">
                当前条件下暂无持仓快照
              </td>
            </tr>
          )}
        </tbody>
      </table>
    </section>
  );
}
