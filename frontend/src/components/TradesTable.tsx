import { useMemo, useState } from 'react';

import type { DailyTradeRecord, QueryGranularity, TradeRecord } from '../types';
import { downloadExcel } from '../utils/excelExport';
import { formatDisplayDateTime, normalizeTimestampKey } from '../utils/datetimeFormat';
import RecordCurveChart, { type RecordCurvePoint } from './RecordCurveChart';

type TradesTableProps = {
  rows: TradeRecord[] | DailyTradeRecord[];
  granularity: QueryGranularity;
  exportBasename?: string;
};

function formatNumber(value: number): string {
  return Number.isFinite(value) ? value.toFixed(2) : '--';
}

function toExcelRows(rows: TradeRecord[] | DailyTradeRecord[], granularity: QueryGranularity): Record<string, unknown>[] {
  if (granularity === 'day') {
    const dailyRows = rows as DailyTradeRecord[];
    return dailyRows.map((row) => ({
      日期: formatDisplayDateTime(row.date),
      买入笔数: row.buy_count,
      卖出笔数: row.sell_count,
      买入金额: row.buy_amount,
      卖出金额: row.sell_amount,
      已实现盈亏: row.realized_pnl,
      手续费: row.commission,
      印花税: row.stamp_duty,
    }));
  }
  const rawRows = rows as TradeRecord[];
  return rawRows.map((row) => ({
    时间: formatDisplayDateTime(row.timestamp),
    股票: row.symbol,
    方向: row.side,
    数量: row.quantity,
    价格: row.price,
    PnL: row.pnl,
    手续费: row.commission ?? '',
    印花税: row.stamp_duty ?? '',
  }));
}

function buildCurvePoints(rows: TradeRecord[] | DailyTradeRecord[], granularity: QueryGranularity): RecordCurvePoint[] {
  if (granularity === 'day') {
    const dailyRows = [...(rows as DailyTradeRecord[])].sort((a, b) => a.date.localeCompare(b.date));
    let cum = 0;
    return dailyRows.map((row) => {
      cum += row.realized_pnl;
      return { label: row.date, value: cum };
    });
  }
  const rawRows = [...(rows as TradeRecord[])].sort((a, b) => normalizeTimestampKey(a.timestamp).localeCompare(normalizeTimestampKey(b.timestamp)));
  let cum = 0;
  return rawRows.map((row) => {
    cum += Number(row.pnl) || 0;
    return { label: row.timestamp, value: cum };
  });
}

export default function TradesTable({ rows, granularity, exportBasename = 'trades' }: TradesTableProps) {
  const [showCurve, setShowCurve] = useState(false);
  const curvePoints = useMemo(() => buildCurvePoints(rows, granularity), [rows, granularity]);

  const toolbar = (
    <div className="button-row table-tool-row">
      <button
        type="button"
        className="secondary-button"
        disabled={rows.length === 0}
        onClick={() => downloadExcel(toExcelRows(rows, granularity), '交易记录', `${exportBasename}-交易记录`)}
      >
        导出 Excel
      </button>
      <button type="button" className="secondary-button" disabled={rows.length === 0} onClick={() => setShowCurve((v) => !v)}>
        {showCurve ? '隐藏曲线' : '生成曲线'}
      </button>
    </div>
  );

  if (granularity === 'day') {
    const dailyRows = rows as DailyTradeRecord[];
    return (
      <section className="table-card compact-card">
        <header className="section-title">交易记录（日聚合）</header>
        {toolbar}
        {showCurve ? (
          <RecordCurveChart title="累计已实现盈亏（按日）" subtitle="按交易日聚合后的累计值" points={curvePoints} />
        ) : null}
        <table className="data-table">
          <thead>
            <tr>
              <th>日期</th>
              <th>买入笔数</th>
              <th>卖出笔数</th>
              <th>买入金额</th>
              <th>卖出金额</th>
              <th>已实现盈亏</th>
              <th>手续费</th>
              <th>印花税</th>
            </tr>
          </thead>
          <tbody>
            {dailyRows.length > 0 ? (
              dailyRows.map((row) => (
                <tr key={row.date}>
                  <td>{formatDisplayDateTime(row.date)}</td>
                  <td>{row.buy_count}</td>
                  <td>{row.sell_count}</td>
                  <td>{formatNumber(row.buy_amount)}</td>
                  <td>{formatNumber(row.sell_amount)}</td>
                  <td>{formatNumber(row.realized_pnl)}</td>
                  <td>{formatNumber(row.commission)}</td>
                  <td>{formatNumber(row.stamp_duty)}</td>
                </tr>
              ))
            ) : (
              <tr>
                <td colSpan={8} className="empty-cell">
                  当前条件下暂无交易聚合数据
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </section>
    );
  }

  const rawRows = rows as TradeRecord[];
  return (
    <section className="table-card compact-card">
      <header className="section-title">交易记录</header>
      {toolbar}
      {showCurve ? <RecordCurveChart title="累计成交盈亏" subtitle="按成交时间排序后的累计 PnL" points={curvePoints} /> : null}
      <table className="data-table">
        <thead>
          <tr>
            <th>时间</th>
            <th>股票</th>
            <th>方向</th>
            <th>数量</th>
            <th>价格</th>
            <th>PnL</th>
          </tr>
        </thead>
        <tbody>
          {rawRows.length > 0 ? (
            rawRows.map((row, index) => (
              <tr key={`${row.timestamp}-${row.symbol}-${index}`}>
                <td>{formatDisplayDateTime(row.timestamp)}</td>
                <td>{row.symbol}</td>
                <td>{row.side}</td>
                <td>{row.quantity}</td>
                <td>{row.price}</td>
                <td>{row.pnl}</td>
              </tr>
            ))
          ) : (
            <tr>
              <td colSpan={6} className="empty-cell">
                当前条件下暂无交易明细
              </td>
            </tr>
          )}
        </tbody>
      </table>
    </section>
  );
}
