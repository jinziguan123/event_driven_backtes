import { useMemo, useState } from 'react';

import type { BenchmarkPoint, DrawdownWindow, EquityPoint } from '../types';
import { formatDisplayDateTime, normalizeTimestampKey, timestampsMatch } from '../utils/datetimeFormat';

type EquityChartProps = {
  equity: EquityPoint[];
  benchmark: BenchmarkPoint[];
  drawdownWindow?: DrawdownWindow;
};

type AxisMode = 'normal' | 'log';
type RangePreset = '1m' | '1y' | 'all' | 'custom';

type ReturnPoint = {
  timestamp: string;
  strategyReturn: number;
  benchmarkReturn: number | null;
  excessReturn: number | null;
};

const width = 1120;
const height = 320;
const verticalPadding = 24;
const rightAxisWidth = 64;
const chartWidth = width - rightAxisWidth;
const tickCount = 6;

function compareTimestampKeys(a: string, b: string): number {
  return normalizeTimestampKey(a).localeCompare(normalizeTimestampKey(b));
}

/** 基准曲线在持久化后行数可能少于权益曲线；按时间前向对齐基准收益，避免整段缺失。 */
function toReturnPoints(equity: EquityPoint[], benchmark: BenchmarkPoint[]): ReturnPoint[] {
  if (equity.length === 0) {
    return [];
  }
  const baseEquity = equity[0].total_equity || 1;
  const sortedBench = [...benchmark].sort((x, y) => compareTimestampKeys(x.timestamp, y.timestamp));
  let j = 0;
  let lastBench: number | null = null;

  return equity.map((item) => {
    const strategyReturn = item.total_equity / baseEquity - 1;
    const tKey = normalizeTimestampKey(item.timestamp);
    while (j < sortedBench.length && normalizeTimestampKey(sortedBench[j].timestamp) <= tKey) {
      lastBench = sortedBench[j].benchmark_return;
      j += 1;
    }
    const benchmarkReturn = lastBench;
    return {
      timestamp: item.timestamp,
      strategyReturn,
      benchmarkReturn,
      excessReturn: benchmarkReturn === null ? null : strategyReturn - benchmarkReturn,
    };
  });
}

function formatPercent(value: number): string {
  return `${(value * 100).toFixed(0)}%`;
}

function getRangeStart(lastTimestamp: string, preset: RangePreset): Date | null {
  if (preset === 'all' || preset === 'custom') {
    return null;
  }
  const end = new Date(lastTimestamp);
  const start = new Date(end);
  if (preset === '1m') {
    start.setDate(start.getDate() - 30);
  }
  if (preset === '1y') {
    start.setFullYear(start.getFullYear() - 1);
  }
  return start;
}

function buildLinePath(values: Array<number | null>, min: number, max: number): string {
  const denominator = max - min || 1;
  return values
    .map((value, index) => {
      if (value === null || Number.isNaN(value)) {
        return null;
      }
      const x = (index / Math.max(values.length - 1, 1)) * chartWidth;
      const y = verticalPadding + (1 - (value - min) / denominator) * (height - verticalPadding * 2);
      return `${index === 0 || values[index - 1] === null ? 'M' : 'L'} ${x.toFixed(2)} ${y.toFixed(2)}`;
    })
    .filter(Boolean)
    .join(' ');
}

function buildAreaPath(values: number[], baseline: number, min: number, max: number): string {
  if (values.length === 0) {
    return '';
  }
  const denominator = max - min || 1;
  const baselineY = verticalPadding + (1 - (baseline - min) / denominator) * (height - verticalPadding * 2);
  const line = values
    .map((value, index) => {
      const x = (index / Math.max(values.length - 1, 1)) * chartWidth;
      const y = verticalPadding + (1 - (value - min) / denominator) * (height - verticalPadding * 2);
      return `${index === 0 ? 'M' : 'L'} ${x.toFixed(2)} ${y.toFixed(2)}`;
    })
    .join(' ');
  return `${line} L ${chartWidth} ${baselineY.toFixed(2)} L 0 ${baselineY.toFixed(2)} Z`;
}

function buildTicks(min: number, max: number): number[] {
  if (min === max) {
    return [min];
  }
  return Array.from({ length: tickCount }, (_, index) => min + ((max - min) * index) / (tickCount - 1));
}

export default function EquityChart({ equity, benchmark, drawdownWindow }: EquityChartProps) {
  const allPoints = useMemo(() => toReturnPoints(equity, benchmark), [equity, benchmark]);
  const [rangePreset, setRangePreset] = useState<RangePreset>('all');
  const [startDate, setStartDate] = useState('');
  const [endDate, setEndDate] = useState('');
  const [showStrategy, setShowStrategy] = useState(true);
  const [showBenchmark, setShowBenchmark] = useState(true);
  const [showExcess, setShowExcess] = useState(true);
  const [axisMode, setAxisMode] = useState<AxisMode>('normal');

  const filteredPoints = useMemo(() => {
    if (allPoints.length === 0) {
      return [];
    }
    const lastTimestamp = allPoints[allPoints.length - 1].timestamp;
    const presetStart = getRangeStart(lastTimestamp, rangePreset);
    return allPoints.filter((point) => {
      const time = new Date(point.timestamp);
      if (presetStart && time < presetStart) {
        return false;
      }
      if (startDate && time < new Date(startDate)) {
        return false;
      }
      if (endDate) {
        const end = new Date(endDate);
        end.setHours(23, 59, 59, 999);
        if (time > end) {
          return false;
        }
      }
      return true;
    });
  }, [allPoints, endDate, rangePreset, startDate]);

  if (filteredPoints.length === 0) {
    return (
      <section className="chart-card compact-card">
        <header className="section-title">收益曲线</header>
        <div className="chart-placeholder">当前回测暂无策略/基准收益曲线数据</div>
      </section>
    );
  }

  function transformValue(value: number | null): number | null {
    if (value === null) {
      return null;
    }
    return axisMode === 'log' ? Math.log1p(value) : value;
  }

  const transformedStrategy = filteredPoints.map((point) => (showStrategy ? transformValue(point.strategyReturn) : null));
  const transformedBenchmark = filteredPoints.map((point) => (showBenchmark ? transformValue(point.benchmarkReturn) : null));
  const transformedExcess = filteredPoints.map((point) => (showExcess ? transformValue(point.excessReturn) : null));
  const nonNullValues = [...transformedStrategy, ...transformedBenchmark, ...transformedExcess].filter((value): value is number => value !== null);
  const min = Math.min(...nonNullValues, transformValue(-0.1) ?? -0.1);
  const max = Math.max(...nonNullValues, transformValue(0.4) ?? 0.4);
  const baseline = transformValue(0) ?? 0;
  const ticks = buildTicks(min, max);
  const strategyPath = buildLinePath(transformedStrategy, min, max);
  const benchmarkPath = buildLinePath(transformedBenchmark, min, max);
  const excessPath = buildLinePath(transformedExcess, min, max);
  const strategyArea = showStrategy
    ? buildAreaPath(
        transformedStrategy.filter((value): value is number => value !== null),
        baseline,
        min,
        max,
      )
    : '';

  const peakIndex = drawdownWindow?.peak_time ? filteredPoints.findIndex((point) => timestampsMatch(point.timestamp, drawdownWindow.peak_time)) : -1;
  const troughIndex = drawdownWindow?.trough_time ? filteredPoints.findIndex((point) => timestampsMatch(point.timestamp, drawdownWindow.trough_time)) : -1;
  const recoveryIndex = drawdownWindow?.recovery_time ? filteredPoints.findIndex((point) => timestampsMatch(point.timestamp, drawdownWindow.recovery_time)) : -1;
  const peakX = peakIndex >= 0 ? (peakIndex / Math.max(filteredPoints.length - 1, 1)) * chartWidth : null;
  const troughX = troughIndex >= 0 ? (troughIndex / Math.max(filteredPoints.length - 1, 1)) * chartWidth : null;
  const recoveryX = recoveryIndex >= 0 ? (recoveryIndex / Math.max(filteredPoints.length - 1, 1)) * chartWidth : null;
  const highlightEnd = recoveryX ?? troughX;

  return (
    <section className="chart-card premium-chart-card">
      <div className="chart-control-bar">
        <div className="control-group inline-group">
          <span className="control-label">缩放</span>
          <button type="button" className={`chart-chip ${rangePreset === '1m' ? 'active' : ''}`} onClick={() => setRangePreset('1m')}>
            1个月
          </button>
          <button type="button" className={`chart-chip ${rangePreset === '1y' ? 'active' : ''}`} onClick={() => setRangePreset('1y')}>
            1年
          </button>
          <button type="button" className={`chart-chip ${rangePreset === 'all' ? 'active' : ''}`} onClick={() => setRangePreset('all')}>
            全部
          </button>
        </div>
        <div className="control-group inline-group">
          <span className="control-label">曲线</span>
          <label className="checkbox-chip"><input type="checkbox" checked={showStrategy} onChange={() => setShowStrategy((value) => !value)} />策略收益</label>
          <label className="checkbox-chip"><input type="checkbox" checked={showBenchmark} onChange={() => setShowBenchmark((value) => !value)} />基准收益</label>
          <label className="checkbox-chip"><input type="checkbox" checked={showExcess} onChange={() => setShowExcess((value) => !value)} />超额收益</label>
        </div>
        <div className="control-group inline-group">
          <label className="radio-chip"><input type="radio" checked={axisMode === 'normal'} onChange={() => setAxisMode('normal')} />普通轴</label>
          <label className="radio-chip"><input type="radio" checked={axisMode === 'log'} onChange={() => setAxisMode('log')} />对数轴</label>
        </div>
        <div className="control-group date-range-group">
          <span className="control-label">时间</span>
          <input type="date" value={startDate} onChange={(event) => { setStartDate(event.target.value); setRangePreset('custom'); }} />
          <span className="date-separator">-</span>
          <input type="date" value={endDate} onChange={(event) => { setEndDate(event.target.value); setRangePreset('custom'); }} />
        </div>
      </div>
      <div className="svg-chart-wrapper premium-wrapper">
        <svg viewBox={`0 0 ${width} ${height}`} className="svg-chart premium-chart" role="img" aria-label="收益对比曲线">
          {ticks.map((tick, index) => {
            const y = verticalPadding + (1 - (tick - min) / (max - min || 1)) * (height - verticalPadding * 2);
            const labelValue = axisMode === 'log' ? Math.expm1(tick) : tick;
            return (
              <g key={`tick-${index}`}>
                <line x1="0" x2={String(chartWidth)} y1={String(y)} y2={String(y)} className="axis-line grid-line" />
                <text x={String(chartWidth + 10)} y={String(y + 4)} className="axis-label">{formatPercent(labelValue)}</text>
              </g>
            );
          })}
          {peakX !== null && highlightEnd !== null && highlightEnd > peakX ? (
            <rect x={peakX} y={verticalPadding} width={highlightEnd - peakX} height={height - verticalPadding * 2} className="drawdown-highlight" />
          ) : null}
          {strategyArea ? <path d={strategyArea} className="strategy-area-fill" /> : null}
          {showStrategy ? <path d={strategyPath} fill="none" stroke="#4a74a8" strokeWidth="3" strokeLinejoin="round" /> : null}
          {showBenchmark ? <path d={benchmarkPath} fill="none" stroke="#b44c43" strokeWidth="2.6" strokeLinejoin="round" /> : null}
          {showExcess ? <path d={excessPath} fill="none" stroke="#f4a340" strokeWidth="2.2" strokeLinejoin="round" strokeDasharray="6 5" /> : null}
          {peakX !== null ? <line x1={String(peakX)} x2={String(peakX)} y1={String(verticalPadding)} y2={String(height - verticalPadding)} className="marker-line" /> : null}
          {troughX !== null ? <line x1={String(troughX)} x2={String(troughX)} y1={String(verticalPadding)} y2={String(height - verticalPadding)} className="marker-line trough" /> : null}
        </svg>
        <div className="chart-bottom-axis">
          <span>{formatDisplayDateTime(filteredPoints[0].timestamp)}</span>
          <span>{formatDisplayDateTime(filteredPoints[filteredPoints.length - 1].timestamp)}</span>
        </div>
        {drawdownWindow ? (
          <div className="chart-caption compact-caption">
            最大回撤：{(drawdownWindow.max_drawdown * 100).toFixed(2)}% ｜ 峰值：{formatDisplayDateTime(drawdownWindow.peak_time)} ｜ 谷值：
            {formatDisplayDateTime(drawdownWindow.trough_time)}
          </div>
        ) : null}
      </div>
    </section>
  );
}
