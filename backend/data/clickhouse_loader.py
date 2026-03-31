from __future__ import annotations

from collections.abc import Callable, Iterable

import pandas as pd

from .db_clients import close_safely, connect_clickhouse, connect_mysql

DEFAULT_BAR_FIELDS = ['open', 'high', 'low', 'close', 'volume', 'amount']


def normalize_symbol(symbol: str) -> str:
    clean = symbol.strip().upper()
    if not clean:
        raise ValueError('symbol 不能为空')
    if '.' in clean:
        return clean

    if len(clean) != 6 or not clean.isdigit():
        raise ValueError(f'无法识别的 symbol: {symbol}')

    if clean.startswith(('5', '6', '9')):
        return f'{clean}.SH'
    if clean.startswith(('0', '1', '2', '3')):
        return f'{clean}.SZ'
    if clean.startswith(('4', '8')):
        return f'{clean}.BJ'
    raise ValueError(f'无法识别市场后缀: {symbol}')


def minute_slot_to_time_text(minute_slot: int) -> str:
    slot = int(minute_slot)
    hour = slot // 60
    minute = slot % 60
    return f'{hour:02d}:{minute:02d}:00'


def _compose_datetime(trade_date, minute_slot: int) -> pd.Timestamp:
    return pd.Timestamp(f'{trade_date} {minute_slot_to_time_text(minute_slot)}')


def _restore_amount(amount_k) -> float:
    if pd.isna(amount_k):
        return 0.0
    return float(amount_k) * 1000.0


def _normalize_fields(fields: list[str] | None) -> list[str]:
    wanted = fields or DEFAULT_BAR_FIELDS
    return [field for field in DEFAULT_BAR_FIELDS if field in wanted]


def _empty_frame(fields: list[str]) -> pd.DataFrame:
    return pd.DataFrame(columns=fields, index=pd.DatetimeIndex([], name='datetime'))


class MysqlSymbolResolver:
    def __init__(self, connection_factory: Callable[[], object] | None = None):
        self._connection_factory = connection_factory or connect_mysql

    def _get_connection(self):
        return self._connection_factory()

    def resolve_symbol_id(self, symbol: str) -> int | None:
        mapping = self.resolve_symbol_ids([symbol])
        normalized = normalize_symbol(symbol)
        return mapping.get(normalized)

    def resolve_symbol_ids(self, symbols: Iterable[str]) -> dict[str, int]:
        normalized_symbols = [normalize_symbol(symbol) for symbol in symbols]
        if not normalized_symbols:
            return {}

        placeholders = ', '.join(['%s'] * len(normalized_symbols))
        connection = self._get_connection()
        try:
            with connection.cursor() as cursor:
                cursor.execute(
                    f'SELECT symbol, symbol_id FROM stock_symbol WHERE symbol IN ({placeholders})',
                    tuple(normalized_symbols),
                )
                rows = cursor.fetchall() or []
            return {str(row['symbol']).upper(): int(row['symbol_id']) for row in rows}
        finally:
            close_safely(connection)


class ClickHouseMinuteBarLoader:
    def __init__(
        self,
        clickhouse_client_factory: Callable[[], object] | None = None,
        mysql_connection_factory: Callable[[], object] | None = None,
        table_name: str = 'stock_bar_1m',
    ):
        self._clickhouse_client_factory = clickhouse_client_factory or connect_clickhouse
        self.symbol_resolver = MysqlSymbolResolver(mysql_connection_factory)
        self.table_name = table_name

    def _get_clickhouse_client(self):
        return self._clickhouse_client_factory()

    def _query_rows(self, sql: str, params: dict, client=None) -> tuple[list, list]:
        own_client = client is None
        ch_client = client or self._get_clickhouse_client()
        try:
            result = ch_client.query(sql, parameters=params)
            rows = list(getattr(result, 'result_rows', []) or [])
            columns = list(getattr(result, 'column_names', []) or [])
            return rows, columns
        finally:
            if own_client:
                close_safely(ch_client)

    def _build_conditions(
        self,
        symbol_id: int,
        start_datetime: str | None,
        end_datetime: str | None,
    ) -> tuple[list[str], dict]:
        conditions = ['symbol_id = {symbol_id:UInt32}']
        params: dict = {'symbol_id': int(symbol_id)}

        if start_datetime:
            start_ts = pd.Timestamp(start_datetime)
            conditions.append(
                '(trade_date > {start_date:Date} OR (trade_date = {start_date:Date} AND minute_slot >= {start_slot:UInt16}))'
            )
            params['start_date'] = start_ts.date()
            params['start_slot'] = int(start_ts.hour * 60 + start_ts.minute)

        if end_datetime:
            end_ts = pd.Timestamp(end_datetime)
            conditions.append(
                '(trade_date < {end_date:Date} OR (trade_date = {end_date:Date} AND minute_slot <= {end_slot:UInt16}))'
            )
            params['end_date'] = end_ts.date()
            params['end_slot'] = int(end_ts.hour * 60 + end_ts.minute)

        return conditions, params

    def _rows_to_frame(self, rows: list, columns: list[str], fields: list[str]) -> pd.DataFrame:
        if not rows:
            return _empty_frame(fields)

        frame = pd.DataFrame(rows, columns=columns)
        frame['datetime'] = [
            _compose_datetime(trade_date, minute_slot)
            for trade_date, minute_slot in zip(frame['trade_date'], frame['minute_slot'])
        ]

        frame['amount'] = frame['amount_k'].map(_restore_amount)
        frame = frame.drop(columns=['trade_date', 'minute_slot', 'amount_k'], errors='ignore')
        frame = frame.set_index('datetime').sort_index()
        frame.index = pd.DatetimeIndex(frame.index, name='datetime')

        selected_cols = [column for column in fields if column in frame.columns]
        result = frame[selected_cols].copy()
        for column in ('open', 'high', 'low', 'close', 'amount'):
            if column in result.columns:
                result[column] = result[column].astype('float32')
        if 'volume' in result.columns:
            result['volume'] = result['volume'].astype('float32')
        return result

    def load_symbol_minutes(
        self,
        symbol: str,
        start_datetime: str | None = None,
        end_datetime: str | None = None,
        fields: list[str] | None = None,
    ) -> pd.DataFrame:
        normalized_symbol = normalize_symbol(symbol)
        selected_fields = _normalize_fields(fields)
        symbol_id = self.symbol_resolver.resolve_symbol_id(normalized_symbol)
        if symbol_id is None:
            return _empty_frame(selected_fields)

        conditions, params = self._build_conditions(symbol_id, start_datetime, end_datetime)
        rows, columns = self._query_rows(
            f'''
            SELECT
                trade_date,
                minute_slot,
                argMax(open, version) AS open,
                argMax(high, version) AS high,
                argMax(low, version) AS low,
                argMax(close, version) AS close,
                argMax(volume, version) AS volume,
                argMax(amount_k, version) AS amount_k
            FROM {self.table_name}
            WHERE {' AND '.join(conditions)}
            GROUP BY trade_date, minute_slot
            ORDER BY trade_date ASC, minute_slot ASC
            ''',
            params=params,
        )
        return self._rows_to_frame(rows, columns, selected_fields)
