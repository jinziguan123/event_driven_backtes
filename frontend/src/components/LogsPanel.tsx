import { useState } from 'react';

import type { LogRecord } from '../types';
import { formatDisplayDateTime } from '../utils/datetimeFormat';

type LogsPanelProps = {
  rows: LogRecord[];
};

export default function LogsPanel({ rows }: LogsPanelProps) {
  const [expanded, setExpanded] = useState(false);
  const latest = rows.length > 0 ? rows[rows.length - 1] : undefined;

  if (rows.length === 0) {
    return (
      <section className="table-card">
        <header className="section-title">运行日志</header>
        <div className="empty-state">当前回测暂无日志</div>
      </section>
    );
  }

  if (!expanded) {
    return (
      <section className="table-card">
        <header className="section-title">运行日志</header>
        <div className="logs-collapsed">
          <div className="log-row log-row-single">
            <span className={`log-level log-${latest!.level.toLowerCase()}`}>{latest!.level}</span>
            <span className="log-time">{formatDisplayDateTime(latest!.timestamp)}</span>
            <span className="log-message">{latest!.message}</span>
          </div>
          {rows.length > 1 ? (
            <button type="button" className="secondary-button logs-expand-btn" onClick={() => setExpanded(true)}>
              展开全部日志（共 {rows.length} 条）
            </button>
          ) : null}
        </div>
      </section>
    );
  }

  return (
    <section className="table-card">
      <header className="section-title">运行日志</header>
      <div className="logs-panel">
        {rows.length > 1 ? (
          <button type="button" className="secondary-button logs-expand-btn" onClick={() => setExpanded(false)}>
            仅显示最新一条
          </button>
        ) : null}
        {rows.map((row, index) => (
          <div key={`${row.timestamp}-${index}`} className="log-row">
            <span className={`log-level log-${row.level.toLowerCase()}`}>{row.level}</span>
            <span className="log-time">{formatDisplayDateTime(row.timestamp)}</span>
            <span className="log-message">{row.message}</span>
          </div>
        ))}
      </div>
    </section>
  );
}
