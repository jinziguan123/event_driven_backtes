import { useEffect, useMemo, useState } from 'react';

import { listBacktests } from '../api/client';
import StatusBadge from '../components/StatusBadge';
import { formatDisplayDateTime } from '../utils/datetimeFormat';
import type { BacktestRun } from '../types';

type BacktestListPageProps = {
  selectedRunId: string | null;
  onSelect: (runId: string) => void;
  onCreateNew: () => void;
  onManagePools: () => void;
  refreshToken: number;
};

export default function BacktestListPage({ selectedRunId, onSelect, onCreateNew, onManagePools, refreshToken }: BacktestListPageProps) {
  const [runs, setRuns] = useState<BacktestRun[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    let canceled = false;
    setLoading(true);
    setError('');

    listBacktests()
      .then((items) => {
        if (!canceled) {
          setRuns(items);
        }
      })
      .catch((reason) => {
        if (!canceled) {
          setError(reason instanceof Error ? reason.message : '加载回测列表失败');
        }
      })
      .finally(() => {
        if (!canceled) {
          setLoading(false);
        }
      });

    return () => {
      canceled = true;
    };
  }, [refreshToken]);

  const runningCount = useMemo(() => runs.filter((run) => run.status === 'RUNNING').length, [runs]);

  return (
    <section className="sidebar-card">
      <div className="sidebar-header">
        <div>
          <div className="panel-kicker">History</div>
          <h2 className="panel-heading">历史回测</h2>
          <p className="panel-subtitle">重数据默认不首屏加载，详情页会按需查询交易记录和持仓快照。</p>
        </div>
      </div>

      <div className="sidebar-actions">
        <button type="button" className="secondary-button primary-like" onClick={onCreateNew}>
          新建回测
        </button>
        <button type="button" className="secondary-button" onClick={onManagePools}>
          股票池管理
        </button>
      </div>

      <div className="sidebar-stats">
        <div className="sidebar-stat-card">
          <span className="sidebar-stat-label">总任务数</span>
          <strong className="sidebar-stat-value">{runs.length}</strong>
        </div>
        <div className="sidebar-stat-card accent">
          <span className="sidebar-stat-label">运行中</span>
          <strong className="sidebar-stat-value">{runningCount}</strong>
        </div>
      </div>

      {loading ? <p className="status-text">正在加载历史回测...</p> : null}
      {error ? <p className="status-text error">{error}</p> : null}

      <div className="list-panel">
        {runs.map((run) => (
          <button
            key={run.run_id}
            type="button"
            className={`list-item ${selectedRunId === run.run_id ? 'active' : ''}`}
            onClick={() => onSelect(run.run_id)}
          >
            <div className="list-item-top">
              <div className="list-title">{run.name || run.run_id}</div>
              <StatusBadge status={run.status} />
            </div>
            <div className="list-subtitle">{run.strategy_name || '未指定策略'}</div>
            <div className="list-meta-grid">
              <span>创建时间</span>
              <span>{formatDisplayDateTime(run.created_at)}</span>
            </div>
            <div className="list-meta-grid emphasis">
              <span>总收益</span>
              <span>{typeof run.total_return === 'number' ? `${(run.total_return * 100).toFixed(2)}%` : '--'}</span>
            </div>
          </button>
        ))}
        {!loading && runs.length === 0 ? <div className="empty-state compact">暂无回测结果，先去新建一个吧。</div> : null}
      </div>
    </section>
  );
}
