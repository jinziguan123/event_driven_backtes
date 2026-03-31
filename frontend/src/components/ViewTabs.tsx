import type { AppView } from '../types';

type ViewTabsProps = {
  activeView: AppView;
  onChange: (view: AppView) => void;
};

const tabs: Array<{ key: AppView; label: string }> = [
  { key: 'history', label: '历史回测' },
  { key: 'create', label: '新建回测' },
];

export default function ViewTabs({ activeView, onChange }: ViewTabsProps) {
  return (
    <div className="view-tabs" role="tablist" aria-label="主视图切换">
      {tabs.map((tab) => (
        <button
          key={tab.key}
          type="button"
          className={`view-tab ${activeView === tab.key ? 'active' : ''}`}
          onClick={() => onChange(tab.key)}
        >
          {tab.label}
        </button>
      ))}
    </div>
  );
}
