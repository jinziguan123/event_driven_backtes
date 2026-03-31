import type { DrawdownWindow } from '../types';
import { formatDisplayDateTime } from '../utils/datetimeFormat';

type DrawdownWindowPanelProps = {
  window?: DrawdownWindow;
};

function formatPercent(value?: number): string {
  if (typeof value !== 'number' || Number.isNaN(value)) {
    return '--';
  }
  return `${(value * 100).toFixed(2)}%`;
}

export default function DrawdownWindowPanel({ window }: DrawdownWindowPanelProps) {
  return (
    <section className="table-card">
      <header className="section-title">最大回撤区间</header>
      <div className="config-grid">
        <div className="config-item">
          <div className="config-key">回撤幅度</div>
          <div className="config-value">{formatPercent(window?.max_drawdown)}</div>
        </div>
        <div className="config-item">
          <div className="config-key">峰值时间</div>
          <div className="config-value">{formatDisplayDateTime(window?.peak_time)}</div>
        </div>
        <div className="config-item">
          <div className="config-key">谷值时间</div>
          <div className="config-value">{formatDisplayDateTime(window?.trough_time)}</div>
        </div>
        <div className="config-item">
          <div className="config-key">恢复时间</div>
          <div className="config-value">{formatDisplayDateTime(window?.recovery_time)}</div>
        </div>
      </div>
    </section>
  );
}
