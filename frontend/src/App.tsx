import { useMemo, useState } from 'react';

import AppHeader from './components/AppHeader';
import Layout from './components/Layout';
import ViewTabs from './components/ViewTabs';
import BacktestCreatePage from './pages/BacktestCreatePage';
import BacktestDetailPage from './pages/BacktestDetailPage';
import BacktestListPage from './pages/BacktestListPage';
import StockPoolManagePage from './pages/StockPoolManagePage';
import type { AppView } from './types';
import './styles.css';

export default function App() {
  const [activeView, setActiveView] = useState<AppView>('history');
  const [selectedRunId, setSelectedRunId] = useState<string | null>(null);
  const [refreshToken, setRefreshToken] = useState(0);

  const toolbarText = useMemo(() => {
    if (activeView === 'pools') {
      return {
        kicker: 'Stock Pools',
        title: '股票池管理',
        subtitle: '维护可复用的命名股票池；新建回测时只需要选择股票池，不再手工维护整段 symbols。',
      };
    }
    return {
      kicker: 'Workspace',
      title: '回测执行与结果查看',
      subtitle: '点击左侧历史回测查看详情，或切换到新建回测发起新的分钟级回测任务。',
    };
  }, [activeView]);

  return (
    <Layout
      header={<AppHeader activeView={activeView} selectedRunId={selectedRunId} />}
      sidebar={
        <BacktestListPage
          selectedRunId={selectedRunId}
          refreshToken={refreshToken}
          onCreateNew={() => setActiveView('create')}
          onManagePools={() => setActiveView('pools')}
          onSelect={(runId) => {
            setSelectedRunId(runId);
            setActiveView('history');
          }}
        />
      }
    >
      <div className="content-stack">
        <div className="content-toolbar panel-card">
          <div>
            <div className="panel-kicker">{toolbarText.kicker}</div>
            <h2 className="panel-heading">{toolbarText.title}</h2>
            <p className="panel-subtitle">{toolbarText.subtitle}</p>
          </div>
          {activeView === 'pools' ? null : <ViewTabs activeView={activeView} onChange={setActiveView} />}
        </div>
        <div className="content-scroll">
          {activeView === 'create' ? (
            <BacktestCreatePage
              onCreated={(runId) => {
                setSelectedRunId(runId);
                setActiveView('history');
                setRefreshToken((value) => value + 1);
              }}
              onOpenStockPools={() => setActiveView('pools')}
            />
          ) : null}
          <div className={activeView === 'history' ? '' : 'view-hidden'}>
            <BacktestDetailPage
              runId={selectedRunId}
              onRunDeleted={(runId) => {
                if (selectedRunId === runId) {
                  setSelectedRunId(null);
                }
                setRefreshToken((value) => value + 1);
              }}
              onRunSettled={() => {
                setRefreshToken((value) => value + 1);
              }}
            />
          </div>
          {activeView === 'pools' ? <StockPoolManagePage /> : null}
        </div>
      </div>
    </Layout>
  );
}
