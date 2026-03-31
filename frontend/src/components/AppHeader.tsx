import type { AppView } from '../types';

type AppHeaderProps = {
  activeView: AppView;
  selectedRunId: string | null;
};

const viewLabelMap: Record<AppView, string> = {
  history: '历史回测',
  create: '新建回测',
  pools: '股票池管理',
};

export default function AppHeader({ activeView, selectedRunId }: AppHeaderProps) {
  return (
    <header className="app-header">
      <div>
        <div className="app-kicker">Event Driven Backtest Studio</div>
        <div className="app-title-row">
          <h1 className="app-title">事件驱动回测工作台</h1>
          <span className="header-pill">分钟线 / 股票池 / 按需查询</span>
        </div>
      </div>
      <div className="header-meta-card">
        <div className="header-meta-label">当前视图</div>
        <div className="header-meta-value">{viewLabelMap[activeView]}</div>
        <div className="header-meta-subtitle">{selectedRunId ? `Run ID：${selectedRunId}` : activeView === 'pools' ? '管理可复用股票池资源' : '请选择历史回测或新建任务'}</div>
      </div>
    </header>
  );
}
