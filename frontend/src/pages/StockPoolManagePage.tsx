import { useEffect, useMemo, useState } from 'react';

import { createStockPool, deleteStockPool, getStockPool, listStockPools, listStocksPage, updateStockPool } from '../api/client';
import type { StockPoolDetail, StockPoolPayload, StockPoolSummary, StockSymbolPage } from '../types';
import { formatDisplayDateTime } from '../utils/datetimeFormat';

const emptyForm: StockPoolPayload = {
  name: '',
  description: '',
  symbols: [],
};

const emptyStockPage: StockSymbolPage = {
  items: [],
  total: 0,
  page: 1,
  page_size: 100,
};

function mergeSymbols(base: string[], next: string[]): string[] {
  const seen = new Set(base);
  const result = [...base];
  for (const symbol of next) {
    if (!seen.has(symbol)) {
      seen.add(symbol);
      result.push(symbol);
    }
  }
  return result;
}

export default function StockPoolManagePage() {
  const [pools, setPools] = useState<StockPoolSummary[]>([]);
  const [selectedPoolId, setSelectedPoolId] = useState<string | null>(null);
  const [form, setForm] = useState<StockPoolPayload>(emptyForm);
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState('');
  const [error, setError] = useState('');

  const [pickerOpen, setPickerOpen] = useState(false);
  const [pickerKeywordInput, setPickerKeywordInput] = useState('');
  const [pickerKeyword, setPickerKeyword] = useState('');
  const [pickerPage, setPickerPage] = useState(1);
  const [pickerPageSize, setPickerPageSize] = useState(100);
  const [pickerData, setPickerData] = useState<StockSymbolPage>(emptyStockPage);
  const [pickerLoading, setPickerLoading] = useState(false);
  const [pickerError, setPickerError] = useState('');
  const [bulkLoading, setBulkLoading] = useState<'filtered' | 'all' | null>(null);

  const isCreating = selectedPoolId === null;

  async function loadPools(selectLatest = false) {
    setLoading(true);
    setError('');
    try {
      const items = await listStockPools();
      setPools(items);
      if (items.length === 0) {
        setSelectedPoolId(null);
        setForm(emptyForm);
      } else if (selectLatest || !selectedPoolId || !items.some((item) => item.pool_id === selectedPoolId)) {
        await handleSelect(items[0].pool_id);
      }
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : '加载股票池失败');
    } finally {
      setLoading(false);
    }
  }

  async function loadPickerPage(options?: { keyword?: string; page?: number; pageSize?: number }) {
    const keyword = options?.keyword ?? pickerKeyword;
    const page = options?.page ?? pickerPage;
    const pageSize = options?.pageSize ?? pickerPageSize;
    setPickerLoading(true);
    setPickerError('');
    try {
      const payload = await listStocksPage({
        keyword: keyword || undefined,
        page,
        pageSize,
      });
      setPickerData(payload);
    } catch (reason) {
      setPickerError(reason instanceof Error ? reason.message : '加载股票列表失败');
    } finally {
      setPickerLoading(false);
    }
  }

  async function fetchAllSymbols(keyword?: string): Promise<string[]> {
    const pageSize = 500;
    let page = 1;
    let total = 0;
    const symbols: string[] = [];

    do {
      const result = await listStocksPage({
        keyword,
        page,
        pageSize,
      });
      total = result.total;
      symbols.push(...result.items.map((item) => item.symbol));
      page += 1;
    } while ((page - 1) * pageSize < total);

    return Array.from(new Set(symbols));
  }

  async function handleSelect(poolId: string) {
    setSelectedPoolId(poolId);
    setError('');
    try {
      const detail = await getStockPool(poolId);
      setForm({
        name: detail.name,
        description: detail.description,
        symbols: detail.symbols,
      });
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : '加载股票池详情失败');
    }
  }

  useEffect(() => {
    void loadPools(true);
    // 组件只在首次挂载时初始化
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  function handleFieldChange(field: keyof StockPoolPayload, value: string) {
    setForm((current) => ({
      ...current,
      [field]: value,
    }));
  }

  function toggleSymbol(symbol: string, checked: boolean) {
    setForm((current) => {
      if (checked) {
        if (current.symbols.includes(symbol)) {
          return current;
        }
        return {
          ...current,
          symbols: [...current.symbols, symbol],
        };
      }
      return {
        ...current,
        symbols: current.symbols.filter((item) => item !== symbol),
      };
    });
  }

  function handleClearSelected() {
    setForm((current) => ({
      ...current,
      symbols: [],
    }));
  }

  function handleOpenPicker() {
    setPickerOpen(true);
    void loadPickerPage({ keyword: pickerKeyword, page: pickerPage, pageSize: pickerPageSize });
  }

  function handleClosePicker() {
    setPickerOpen(false);
  }

  function handleSearchStocks() {
    const keyword = pickerKeywordInput.trim().toUpperCase();
    setPickerKeyword(keyword);
    setPickerPage(1);
    void loadPickerPage({ keyword, page: 1, pageSize: pickerPageSize });
  }

  function handlePageChange(nextPage: number) {
    setPickerPage(nextPage);
    void loadPickerPage({ page: nextPage });
  }

  function handlePageSizeChange(nextSize: number) {
    setPickerPageSize(nextSize);
    setPickerPage(1);
    void loadPickerPage({ page: 1, pageSize: nextSize });
  }

  function handleToggleCurrentPage(checked: boolean) {
    const currentSymbols = pickerData.items.map((item) => item.symbol);
    if (checked) {
      setForm((current) => ({
        ...current,
        symbols: mergeSymbols(current.symbols, currentSymbols),
      }));
      return;
    }
    setForm((current) => ({
      ...current,
      symbols: current.symbols.filter((symbol) => !currentSymbols.includes(symbol)),
    }));
  }

  async function handleSelectAllFiltered() {
    setBulkLoading('filtered');
    setPickerError('');
    try {
      const symbols = await fetchAllSymbols(pickerKeyword || undefined);
      setForm((current) => ({
        ...current,
        symbols: mergeSymbols(current.symbols, symbols),
      }));
    } catch (reason) {
      setPickerError(reason instanceof Error ? reason.message : '批量选择筛选结果失败');
    } finally {
      setBulkLoading(null);
    }
  }

  async function handleSelectAllMarket() {
    if (!window.confirm('将选择全市场全部股票（5000+），确认继续？')) {
      return;
    }
    setBulkLoading('all');
    setPickerError('');
    try {
      const symbols = await fetchAllSymbols(undefined);
      setForm((current) => ({
        ...current,
        symbols: mergeSymbols(current.symbols, symbols),
      }));
    } catch (reason) {
      setPickerError(reason instanceof Error ? reason.message : '全市场选择失败');
    } finally {
      setBulkLoading(null);
    }
  }

  async function handleSave() {
    if (!form.name.trim()) {
      setError('股票池名称不能为空');
      return;
    }
    setSaving(true);
    setError('');
    setMessage('');
    try {
      let detail: StockPoolDetail;
      if (isCreating) {
        detail = await createStockPool(form);
        setMessage(`已创建股票池：${detail.name}`);
      } else {
        detail = await updateStockPool(selectedPoolId, form);
        setMessage(`已更新股票池：${detail.name}`);
      }
      await loadPools();
      setSelectedPoolId(detail.pool_id);
      setForm({ name: detail.name, description: detail.description, symbols: detail.symbols });
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : '保存股票池失败');
    } finally {
      setSaving(false);
    }
  }

  async function handleDelete() {
    if (!selectedPoolId) {
      return;
    }
    setSaving(true);
    setError('');
    setMessage('');
    try {
      await deleteStockPool(selectedPoolId);
      setMessage('股票池已删除');
      setSelectedPoolId(null);
      setForm(emptyForm);
      await loadPools(true);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : '删除股票池失败');
    } finally {
      setSaving(false);
    }
  }

  function handleCreateNew() {
    setSelectedPoolId(null);
    setForm(emptyForm);
    setError('');
    setMessage('');
  }

  const totalPages = useMemo(
    () => Math.max(1, Math.ceil((pickerData.total || 0) / Math.max(pickerData.page_size || pickerPageSize, 1))),
    [pickerData.page_size, pickerData.total, pickerPageSize],
  );
  const currentPageAllSelected =
    pickerData.items.length > 0 && pickerData.items.every((item) => form.symbols.includes(item.symbol));

  return (
    <div className="stock-pool-layout">
      <section className="panel-card stock-pool-list-card">
        <div className="sidebar-header">
          <div>
            <div className="panel-kicker">Pools</div>
            <h2 className="panel-heading">股票池列表</h2>
            <p className="panel-subtitle">股票池会独立持久化，下次创建回测时可直接复用。</p>
          </div>
          <button type="button" className="secondary-button primary-like" onClick={handleCreateNew}>
            新建股票池
          </button>
        </div>
        {loading ? <p className="status-text">正在加载股票池...</p> : null}
        {error ? <p className="status-text error">{error}</p> : null}
        <div className="list-panel">
          {pools.map((pool) => (
            <button
              key={pool.pool_id}
              type="button"
              className={`list-item ${selectedPoolId === pool.pool_id ? 'active' : ''}`}
              onClick={() => void handleSelect(pool.pool_id)}
            >
              <div className="list-title">{pool.name}</div>
              <div className="list-subtitle">{pool.description || '未填写描述'}</div>
              <div className="list-meta-grid">
                <span>股票数量</span>
                <span>{pool.symbol_count}</span>
              </div>
              <div className="list-meta-grid">
                <span>更新时间</span>
                <span>{formatDisplayDateTime(pool.updated_at)}</span>
              </div>
            </button>
          ))}
          {!loading && pools.length === 0 ? <div className="empty-state compact">还没有股票池，先新建一个吧。</div> : null}
        </div>
      </section>

      <section className="panel-card stock-pool-editor-card">
        <div className="page-header compact">
          <h2>{isCreating ? '新建股票池' : '编辑股票池'}</h2>
          <p>编辑时通过悬浮选择器分页选股，支持全市场一键全选。</p>
        </div>
        <div className="stock-pool-form-grid">
          <label>
            <span>股票池名称</span>
            <input value={form.name} onChange={(event) => handleFieldChange('name', event.target.value)} placeholder="如：双均线观察池" />
          </label>
          <label>
            <span>备注说明</span>
            <input value={form.description} onChange={(event) => handleFieldChange('description', event.target.value)} placeholder="如：分钟级趋势策略候选池" />
          </label>
          <div className="full-span stock-picker-entry">
            <div className="stock-picker-entry-row">
              <span className="stock-selector-label">股票选择</span>
              <div className="button-row">
                <button type="button" className="secondary-button" onClick={handleOpenPicker}>
                  打开悬浮选择器
                </button>
                <button type="button" className="secondary-button" onClick={handleClearSelected} disabled={form.symbols.length === 0}>
                  清空已选
                </button>
              </div>
            </div>
            <p className="panel-subtitle">已选 {form.symbols.length} 支股票。点击“打开悬浮选择器”进行分页检索和批量操作。</p>
          </div>
        </div>
        <div className="form-actions between">
          <div>
            {message ? <p className="status-text">{message}</p> : null}
            {error ? <p className="status-text error">{error}</p> : null}
          </div>
          <div className="button-row">
            {!isCreating ? (
              <button type="button" className="secondary-button danger-button" onClick={() => void handleDelete()} disabled={saving}>
                删除
              </button>
            ) : null}
            <button type="button" onClick={() => void handleSave()} disabled={saving}>
              {saving ? '保存中...' : isCreating ? '创建股票池' : '保存修改'}
            </button>
          </div>
        </div>
      </section>

      {pickerOpen ? (
        <div className="stock-picker-overlay" role="dialog" aria-modal="true" aria-label="股票选择器">
          <div className="stock-picker-modal">
            <div className="stock-picker-header">
              <div>
                <h3>股票选择器</h3>
                <p>
                  当前筛选：{pickerKeyword || '全部'} ｜ 已选 {form.symbols.length} ｜ 总数 {pickerData.total}
                </p>
              </div>
              <button type="button" className="secondary-button" onClick={handleClosePicker}>
                关闭
              </button>
            </div>

            <div className="stock-picker-toolbar">
              <input
                value={pickerKeywordInput}
                onChange={(event) => setPickerKeywordInput(event.target.value.toUpperCase())}
                placeholder="输入代码过滤，如 000001 / 6005"
              />
              <button type="button" className="secondary-button" onClick={handleSearchStocks} disabled={pickerLoading}>
                {pickerLoading ? '搜索中...' : '搜索'}
              </button>
              <button type="button" className="secondary-button" onClick={() => handleToggleCurrentPage(!currentPageAllSelected)} disabled={pickerData.items.length === 0}>
                {currentPageAllSelected ? '取消当前页' : '全选当前页'}
              </button>
              <button type="button" className="secondary-button" onClick={() => void handleSelectAllFiltered()} disabled={bulkLoading !== null}>
                {bulkLoading === 'filtered' ? '处理中...' : '全选筛选结果'}
              </button>
              <button type="button" className="secondary-button" onClick={() => void handleSelectAllMarket()} disabled={bulkLoading !== null}>
                {bulkLoading === 'all' ? '处理中...' : '全市场全选'}
              </button>
            </div>

            {pickerError ? <p className="status-text error">{pickerError}</p> : null}
            {pickerLoading ? <p className="status-text">正在加载股票列表...</p> : null}

            <div className="stock-picker-grid">
              {pickerData.items.map((item) => {
                const checked = form.symbols.includes(item.symbol);
                return (
                  <label key={item.symbol} className={`stock-option-item ${checked ? 'checked' : ''}`}>
                    <input type="checkbox" checked={checked} onChange={(event) => toggleSymbol(item.symbol, event.target.checked)} />
                    <span>{item.symbol}</span>
                  </label>
                );
              })}
              {!pickerLoading && pickerData.items.length === 0 ? <div className="empty-state compact">当前筛选没有结果。</div> : null}
            </div>

            <div className="stock-picker-footer">
              <div className="stock-picker-page-size">
                <span>每页</span>
                <select value={pickerPageSize} onChange={(event) => handlePageSizeChange(Number(event.target.value))}>
                  <option value={50}>50</option>
                  <option value={100}>100</option>
                  <option value={200}>200</option>
                </select>
              </div>
              <div className="stock-picker-pagination">
                <button type="button" className="secondary-button" onClick={() => handlePageChange(Math.max(1, pickerPage - 1))} disabled={pickerPage <= 1 || pickerLoading}>
                  上一页
                </button>
                <span>
                  第 {pickerPage} / {totalPages} 页
                </span>
                <button type="button" className="secondary-button" onClick={() => handlePageChange(Math.min(totalPages, pickerPage + 1))} disabled={pickerPage >= totalPages || pickerLoading}>
                  下一页
                </button>
              </div>
            </div>
          </div>
        </div>
      ) : null}
    </div>
  );
}
