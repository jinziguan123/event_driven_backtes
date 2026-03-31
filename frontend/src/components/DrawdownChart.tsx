import type { DrawdownPoint, DrawdownWindow } from '../types';
import { timestampsMatch } from '../utils/datetimeFormat';

type DrawdownChartProps = {
  rows: DrawdownPoint[];
  drawdownWindow?: DrawdownWindow;
};

function buildPath(values: Array<number | null>, width: number, height: number, min: number, max: number): string {
  const denominator = max - min || 1;
  return values
    .map((value, index) => {
      if (value === null || Number.isNaN(value)) {
        return null;
      }
      const x = (index / Math.max(values.length - 1, 1)) * width;
      const y = height - ((value - min) / denominator) * height;
      return `${index === 0 || values[index - 1] === null ? 'M' : 'L'} ${x.toFixed(2)} ${y.toFixed(2)}`;
    })
    .filter(Boolean)
    .join(' ');
}

function findValueRange(values: number[], defaultMin: number, defaultMax: number): { min: number; max: number } {
  let min = defaultMin;
  let max = defaultMax;

  for (const value of values) {
    if (Number.isNaN(value)) {
      continue;
    }
    if (value < min) {
      min = value;
    }
    if (value > max) {
      max = value;
    }
  }

  return { min, max };
}

function findX(timestamp: string | null | undefined, rows: DrawdownPoint[], width: number): number | null {
  if (!timestamp) {
    return null;
  }
  const index = rows.findIndex((row) => timestampsMatch(row.timestamp, timestamp));
  if (index < 0) {
    return null;
  }
  return (index / Math.max(rows.length - 1, 1)) * width;
}

export default function DrawdownChart({ rows, drawdownWindow }: DrawdownChartProps) {
  const width = 880;
  const height = 220;

  if (rows.length === 0) {
    return (
      <section className="chart-card">
        <header className="section-title">回撤曲线</header>
        <div className="chart-placeholder">当前回测暂无回撤曲线数据</div>
      </section>
    );
  }

  const values = rows.flatMap((row) => [row.strategy_drawdown, row.benchmark_drawdown ?? null]).filter((value): value is number => value !== null);
  const { min, max } = findValueRange(values, -0.01, 0);
  const strategyPath = buildPath(rows.map((row) => row.strategy_drawdown), width, height, min, max);
  const benchmarkPath = buildPath(rows.map((row) => row.benchmark_drawdown ?? null), width, height, min, max);
  const peakX = findX(drawdownWindow?.peak_time, rows, width);
  const troughX = findX(drawdownWindow?.trough_time, rows, width);
  const recoveryX = findX(drawdownWindow?.recovery_time, rows, width);
  const highlightEnd = recoveryX ?? troughX;
  const zeroY = height - ((0 - min) / (max - min || 1)) * height;

  return (
    <section className="chart-card">
      <header className="chart-header">
        <div>
          <div className="section-title">回撤曲线</div>
          <div className="chart-caption">单独展示策略与基准回撤，并高亮最大回撤窗口。</div>
        </div>
      </header>
      <div className="svg-chart-wrapper">
        <svg viewBox={`0 0 ${width} ${height}`} className="svg-chart" role="img" aria-label="回撤曲线">
          {peakX !== null && highlightEnd !== null && highlightEnd > peakX ? (
            <rect x={peakX} y={0} width={highlightEnd - peakX} height={height} className="drawdown-highlight" />
          ) : null}
          <line x1="0" x2={String(width)} y1={String(zeroY)} y2={String(zeroY)} className="axis-line" />
          <path d={strategyPath} fill="none" stroke="#dc2626" strokeWidth="3" strokeLinejoin="round" />
          {benchmarkPath ? <path d={benchmarkPath} fill="none" stroke="#f59e0b" strokeWidth="2.5" strokeLinejoin="round" /> : null}
          {troughX !== null ? <line x1={String(troughX)} x2={String(troughX)} y1="0" y2={String(height)} className="marker-line trough" /> : null}
        </svg>
      </div>
    </section>
  );
}
