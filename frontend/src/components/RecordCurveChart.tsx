import { formatDisplayDateTime } from '../utils/datetimeFormat';

export type RecordCurvePoint = { label: string; value: number };

type RecordCurveChartProps = {
  title: string;
  subtitle?: string;
  points: RecordCurvePoint[];
};

export default function RecordCurveChart({ title, subtitle, points }: RecordCurveChartProps) {
  if (points.length === 0) {
    return (
      <div className="record-curve-wrap">
        <div className="section-title">{title}</div>
        <div className="chart-placeholder">暂无可用数据点</div>
      </div>
    );
  }

  const width = 840;
  const height = 200;
  const padX = 8;
  const padY = 12;
  const values = points.map((p) => p.value);
  let min = Math.min(...values);
  let max = Math.max(...values);
  if (min === max) {
    min -= 1;
    max += 1;
  }
  const span = max - min || 1;
  const path = points
    .map((p, i) => {
      const x = padX + (i / Math.max(points.length - 1, 1)) * (width - padX * 2);
      const y = padY + (1 - (p.value - min) / span) * (height - padY * 2);
      return `${i === 0 ? 'M' : 'L'} ${x.toFixed(2)} ${y.toFixed(2)}`;
    })
    .join(' ');

  const startLabel = formatDisplayDateTime(points[0].label);
  const endLabel = formatDisplayDateTime(points[points.length - 1].label);

  return (
    <div className="record-curve-wrap">
      <div className="section-title">{title}</div>
      {subtitle ? <div className="chart-caption">{subtitle}</div> : null}
      <div className="svg-chart-wrapper">
        <svg viewBox={`0 0 ${width} ${height}`} className="svg-chart" role="img" aria-label={title}>
          <path d={path} fill="none" stroke="#4a74a8" strokeWidth="2.5" strokeLinejoin="round" />
        </svg>
        <div className="chart-bottom-axis">
          <span>{startLabel}</span>
          <span>{endLabel}</span>
        </div>
      </div>
    </div>
  );
}
