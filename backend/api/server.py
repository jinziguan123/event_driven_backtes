from __future__ import annotations

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import StreamingResponse

from event_driven_backtest.backend.api.schemas import (
    BacktestProfileResponse,
    BacktestCancelResponse,
    BacktestCreateRequest,
    BacktestCreateResponse,
    BacktestDeleteResponse,
    StockPoolCreateRequest,
    StockPoolResponse,
    StockSymbolPageResponse,
    StockSymbolOption,
    StockPoolSummary,
    StockPoolUpdateRequest,
    StrategySummary,
)
from event_driven_backtest.backend.runner.service import BacktestService

app = FastAPI(title='事件驱动回测 API')
service = BacktestService()


@app.get('/api/strategies', response_model=list[StrategySummary])
def list_strategies():
    return service.list_strategies()


@app.get('/api/stock-pools', response_model=list[StockPoolSummary])
def list_stock_pools():
    return service.list_stock_pools()


@app.get('/api/stocks', response_model=list[StockSymbolOption])
def list_stocks(
    keyword: str | None = Query(default=None),
    limit: int = Query(default=200, ge=1, le=5000),
):
    return service.list_stocks(keyword=keyword, limit=limit)


@app.get('/api/stocks/page', response_model=StockSymbolPageResponse)
def list_stocks_page(
    keyword: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=100, ge=1, le=500),
):
    return service.list_stocks_page(keyword=keyword, page=page, page_size=page_size)


@app.post('/api/stock-pools', response_model=StockPoolResponse)
def create_stock_pool(payload: StockPoolCreateRequest):
    return service.create_stock_pool(payload.model_dump())


@app.get('/api/stock-pools/{pool_id}', response_model=StockPoolResponse)
def get_stock_pool(pool_id: str):
    result = service.get_stock_pool(pool_id)
    if result is None:
        raise HTTPException(status_code=404, detail='未找到股票池')
    return result


@app.put('/api/stock-pools/{pool_id}', response_model=StockPoolResponse)
def update_stock_pool(pool_id: str, payload: StockPoolUpdateRequest):
    result = service.update_stock_pool(pool_id, payload.model_dump())
    if result is None:
        raise HTTPException(status_code=404, detail='未找到股票池')
    return result


@app.delete('/api/stock-pools/{pool_id}')
def delete_stock_pool(pool_id: str):
    deleted = service.delete_stock_pool(pool_id)
    if not deleted:
        raise HTTPException(status_code=404, detail='未找到股票池')
    return {'pool_id': pool_id, 'deleted': True}


@app.get('/api/backtests')
def list_backtests():
    return service.list_runs()


@app.post('/api/backtests', response_model=BacktestCreateResponse)
def create_backtest(payload: BacktestCreateRequest):
    return service.create_run(payload.model_dump())


@app.post('/api/backtests/{run_id}/cancel', response_model=BacktestCancelResponse)
def cancel_backtest(run_id: str):
    result = service.cancel_run(run_id)
    if result is None:
        raise HTTPException(status_code=404, detail='未找到回测结果')
    return result


@app.delete('/api/backtests/{run_id}', response_model=BacktestDeleteResponse)
def delete_backtest(run_id: str):
    result = service.delete_run(run_id)
    if result is None:
        raise HTTPException(status_code=404, detail='未找到回测结果')
    if not result.get('deleted'):
        raise HTTPException(status_code=409, detail=result.get('message') or '删除回测记录失败')
    return result


@app.get('/api/backtests/{run_id}')
def get_backtest_detail(run_id: str):
    result = service.get_run(run_id)
    if result is None:
        raise HTTPException(status_code=404, detail='未找到回测结果')
    return result


@app.get('/api/backtests/{run_id}/profile', response_model=BacktestProfileResponse)
def get_backtest_profile(run_id: str):
    result = service.get_run_profile(run_id)
    if result is None:
        raise HTTPException(status_code=404, detail='未找到回测结果')
    return result


@app.get('/api/backtests/{run_id}/stream')
def stream_backtest(run_id: str):
    stream = service.stream_run(run_id)
    if stream is None:
        raise HTTPException(status_code=404, detail='未找到回测结果')
    return StreamingResponse(
        stream,
        media_type='text/event-stream',
        headers={
            'Cache-Control': 'no-cache',
            'Connection': 'keep-alive',
            'X-Accel-Buffering': 'no',
        },
    )


@app.get('/api/backtests/{run_id}/equity')
def get_backtest_equity(run_id: str):
    return service.get_equity(run_id)


@app.get('/api/backtests/{run_id}/benchmark')
def get_backtest_benchmark(run_id: str):
    return service.get_benchmark(run_id)


@app.get('/api/backtests/{run_id}/drawdown')
def get_backtest_drawdown(run_id: str):
    return service.get_drawdown(run_id)


@app.get('/api/backtests/{run_id}/trades')
def get_backtest_trades(
    run_id: str,
    start_date: str | None = Query(default=None),
    end_date: str | None = Query(default=None),
    granularity: str = Query(default='raw'),
):
    return service.get_trades(run_id, start_date=start_date, end_date=end_date, granularity=granularity)


@app.get('/api/backtests/{run_id}/positions')
def get_backtest_positions(
    run_id: str,
    start_date: str | None = Query(default=None),
    end_date: str | None = Query(default=None),
    granularity: str = Query(default='raw'),
):
    return service.get_positions(run_id, start_date=start_date, end_date=end_date, granularity=granularity)


@app.get('/api/backtests/{run_id}/logs')
def get_backtest_logs(run_id: str):
    return service.get_logs(run_id)
