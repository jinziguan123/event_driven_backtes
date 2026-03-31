from __future__ import annotations

from datetime import datetime
import os
from pathlib import Path
from uuid import uuid4
import warnings

from event_driven_backtest.backend.data.db_clients import close_safely, connect_mysql
from event_driven_backtest.backend.storage.db import DEFAULT_DB_PATH, connect_db, init_db

_MYSQL_FALLBACK_WARNING_EMITTED = False


def _to_bool(value: str | None, default: bool = True) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {'1', 'true', 'yes', 'on'}


def _json_ready(value):
    if isinstance(value, datetime):
        return value.isoformat()
    return value


class StockPoolStore:
    def __init__(
        self,
        db_path: str | Path = DEFAULT_DB_PATH,
        backend: str | None = None,
        owner_key: str | None = None,
        mysql_connection_factory=None,
    ):
        self.db_path = Path(db_path)
        self.owner_key = owner_key or os.environ.get('EVENT_BT_OWNER_KEY', 'default')
        self._mysql_connection_factory = mysql_connection_factory or connect_mysql
        self.backend = self._resolve_backend(backend)
        if self.backend == 'sqlite':
            init_db(self.db_path)

    def _resolve_backend(self, backend: str | None) -> str:
        preferred = (backend or os.environ.get('EVENT_BT_STOCK_POOL_BACKEND', 'mysql')).strip().lower()
        if preferred not in {'mysql', 'sqlite'}:
            raise ValueError(f'不支持的股票池存储后端: {preferred}')
        if preferred == 'sqlite':
            return 'sqlite'

        connection = None
        try:
            connection = self._get_mysql_connection()
            with connection.cursor() as cursor:
                cursor.execute('SELECT 1')
                cursor.fetchone()
            return 'mysql'
        except Exception as exc:
            allow_fallback = _to_bool(os.environ.get('EVENT_BT_STOCK_POOL_ALLOW_SQLITE_FALLBACK'), default=False)
            if not allow_fallback:
                raise RuntimeError('MySQL 股票池存储不可用，且已禁用 SQLite 回退') from exc
            global _MYSQL_FALLBACK_WARNING_EMITTED
            if not _MYSQL_FALLBACK_WARNING_EMITTED:
                warnings.warn(
                    f'MySQL 股票池存储不可用，已自动回退 SQLite: {exc}',
                    RuntimeWarning,
                    stacklevel=2,
                )
                _MYSQL_FALLBACK_WARNING_EMITTED = True
            return 'sqlite'
        finally:
            if connection is not None:
                close_safely(connection)

    def _get_mysql_connection(self):
        return self._mysql_connection_factory()

    def list_pools(self) -> list[dict]:
        if self.backend == 'mysql':
            return self._list_pools_mysql()
        return self._list_pools_sqlite()

    def get_pool(self, pool_id: str) -> dict | None:
        if self.backend == 'mysql':
            return self._get_pool_mysql(pool_id)
        return self._get_pool_sqlite(pool_id)

    def create_pool(self, name: str, description: str, symbols: list[str]) -> dict:
        if self.backend == 'mysql':
            return self._create_pool_mysql(name, description, symbols)
        return self._create_pool_sqlite(name, description, symbols)

    def update_pool(self, pool_id: str, name: str, description: str, symbols: list[str]) -> dict | None:
        if self.backend == 'mysql':
            return self._update_pool_mysql(pool_id, name, description, symbols)
        return self._update_pool_sqlite(pool_id, name, description, symbols)

    def delete_pool(self, pool_id: str) -> bool:
        if self.backend == 'mysql':
            return self._delete_pool_mysql(pool_id)
        return self._delete_pool_sqlite(pool_id)

    def get_pool_symbols(self, pool_id: str) -> list[str]:
        pool = self.get_pool(pool_id)
        if pool is None:
            return []
        return pool['symbols']

    def list_symbols(self, keyword: str | None = None, limit: int = 200, offset: int = 0) -> list[dict]:
        safe_limit = min(max(int(limit), 1), 5000)
        safe_offset = max(int(offset), 0)
        clean_keyword = (keyword or '').strip().upper()
        if self.backend == 'mysql':
            return self._list_symbols_mysql(clean_keyword, safe_limit, safe_offset)
        return self._list_symbols_sqlite(clean_keyword, safe_limit, safe_offset)

    def count_symbols(self, keyword: str | None = None) -> int:
        clean_keyword = (keyword or '').strip().upper()
        if self.backend == 'mysql':
            return self._count_symbols_mysql(clean_keyword)
        return self._count_symbols_sqlite(clean_keyword)

    def _list_pools_sqlite(self) -> list[dict]:
        with connect_db(self.db_path) as conn:
            rows = conn.execute(
                '''
                SELECT p.pool_id, p.name, p.description, p.created_at, p.updated_at, COUNT(s.symbol) AS symbol_count
                FROM stock_pools p
                LEFT JOIN stock_pool_symbols s ON p.pool_id = s.pool_id
                GROUP BY p.pool_id
                ORDER BY p.updated_at DESC, p.created_at DESC
                '''
            ).fetchall()
        return [dict(row) for row in rows]

    def _get_pool_sqlite(self, pool_id: str) -> dict | None:
        with connect_db(self.db_path) as conn:
            row = conn.execute(
                'SELECT pool_id, name, description, created_at, updated_at FROM stock_pools WHERE pool_id = ?',
                (pool_id,),
            ).fetchone()
            if row is None:
                return None
            symbol_rows = conn.execute(
                'SELECT symbol FROM stock_pool_symbols WHERE pool_id = ? ORDER BY sort_order ASC, symbol ASC',
                (pool_id,),
            ).fetchall()
        payload = dict(row)
        payload['symbols'] = [item['symbol'] for item in symbol_rows]
        payload['symbol_count'] = len(payload['symbols'])
        return payload

    def _create_pool_sqlite(self, name: str, description: str, symbols: list[str]) -> dict:
        pool_id = uuid4().hex[:12]
        now = datetime.now().isoformat()
        clean_symbols = self._normalize_symbols(symbols)
        with connect_db(self.db_path) as conn:
            conn.execute(
                'INSERT INTO stock_pools(pool_id, name, description, created_at, updated_at) VALUES(?, ?, ?, ?, ?)',
                (pool_id, name, description, now, now),
            )
            conn.executemany(
                'INSERT INTO stock_pool_symbols(pool_id, symbol, sort_order) VALUES(?, ?, ?)',
                [(pool_id, symbol, index) for index, symbol in enumerate(clean_symbols)],
            )
            conn.commit()
        return self.get_pool(pool_id) or {}

    def _update_pool_sqlite(self, pool_id: str, name: str, description: str, symbols: list[str]) -> dict | None:
        now = datetime.now().isoformat()
        clean_symbols = self._normalize_symbols(symbols)
        with connect_db(self.db_path) as conn:
            exists = conn.execute('SELECT 1 FROM stock_pools WHERE pool_id = ?', (pool_id,)).fetchone()
            if exists is None:
                return None
            conn.execute(
                'UPDATE stock_pools SET name = ?, description = ?, updated_at = ? WHERE pool_id = ?',
                (name, description, now, pool_id),
            )
            conn.execute('DELETE FROM stock_pool_symbols WHERE pool_id = ?', (pool_id,))
            conn.executemany(
                'INSERT INTO stock_pool_symbols(pool_id, symbol, sort_order) VALUES(?, ?, ?)',
                [(pool_id, symbol, index) for index, symbol in enumerate(clean_symbols)],
            )
            conn.commit()
        return self.get_pool(pool_id)

    def _delete_pool_sqlite(self, pool_id: str) -> bool:
        with connect_db(self.db_path) as conn:
            conn.execute('DELETE FROM stock_pool_symbols WHERE pool_id = ?', (pool_id,))
            cursor = conn.execute('DELETE FROM stock_pools WHERE pool_id = ?', (pool_id,))
            conn.commit()
        return cursor.rowcount > 0

    def _list_symbols_sqlite(self, keyword: str, limit: int, offset: int) -> list[dict]:
        conditions: list[str] = []
        params: list[object] = []
        if keyword:
            conditions.append('symbol LIKE ?')
            params.append(f'%{keyword}%')
        where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ''
        query = f'''
            SELECT DISTINCT symbol
            FROM stock_pool_symbols
            {where_clause}
            ORDER BY symbol ASC
            LIMIT ?
            OFFSET ?
        '''
        params.extend([limit, offset])
        with connect_db(self.db_path) as conn:
            rows = conn.execute(query, tuple(params)).fetchall()
        return [{'symbol': str(row['symbol']).upper()} for row in rows]

    def _count_symbols_sqlite(self, keyword: str) -> int:
        conditions: list[str] = []
        params: list[object] = []
        if keyword:
            conditions.append('symbol LIKE ?')
            params.append(f'%{keyword}%')
        where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ''
        query = f'''
            SELECT COUNT(*) AS total
            FROM (SELECT DISTINCT symbol FROM stock_pool_symbols {where_clause}) t
        '''
        with connect_db(self.db_path) as conn:
            row = conn.execute(query, tuple(params)).fetchone()
        return int(row['total']) if row is not None else 0

    def _list_pools_mysql(self) -> list[dict]:
        connection = self._get_mysql_connection()
        try:
            with connection.cursor() as cursor:
                cursor.execute(
                    '''
                    SELECT
                        p.pool_id,
                        p.pool_name AS name,
                        COALESCE(p.description, '') AS description,
                        p.created_at,
                        p.updated_at,
                        COUNT(s.symbol_id) AS symbol_count
                    FROM stock_pool p
                    LEFT JOIN stock_pool_symbol s ON p.pool_id = s.pool_id
                    WHERE p.owner_key = %s AND p.is_active = 1
                    GROUP BY p.pool_id, p.pool_name, p.description, p.created_at, p.updated_at
                    ORDER BY p.updated_at DESC, p.created_at DESC
                    ''',
                    (self.owner_key,),
                )
                rows = cursor.fetchall() or []
            payload_rows = []
            for row in rows:
                normalized = {key: _json_ready(value) for key, value in row.items()}
                normalized['pool_id'] = str(normalized['pool_id'])
                payload_rows.append(normalized)
            return payload_rows
        finally:
            close_safely(connection)

    def _get_pool_mysql(self, pool_id: str) -> dict | None:
        connection = self._get_mysql_connection()
        try:
            with connection.cursor() as cursor:
                cursor.execute(
                    '''
                    SELECT
                        pool_id,
                        pool_name AS name,
                        COALESCE(description, '') AS description,
                        created_at,
                        updated_at
                    FROM stock_pool
                    WHERE owner_key = %s AND pool_id = %s AND is_active = 1
                    ''',
                    (self.owner_key, int(pool_id)),
                )
                pool_row = cursor.fetchone()
                if pool_row is None:
                    return None

                cursor.execute(
                    '''
                    SELECT ss.symbol
                    FROM stock_pool_symbol sps
                    INNER JOIN stock_symbol ss ON sps.symbol_id = ss.symbol_id
                    WHERE sps.pool_id = %s
                    ORDER BY sps.sort_order ASC, ss.symbol ASC
                    ''',
                    (int(pool_id),),
                )
                symbol_rows = cursor.fetchall() or []
            payload = {key: _json_ready(value) for key, value in pool_row.items()}
            payload['pool_id'] = str(payload['pool_id'])
            payload['symbols'] = [str(item['symbol']).upper() for item in symbol_rows]
            payload['symbol_count'] = len(payload['symbols'])
            return payload
        finally:
            close_safely(connection)

    def _resolve_symbol_ids_mysql(self, symbols: list[str], cursor) -> list[int]:
        if not symbols:
            return []
        placeholders = ', '.join(['%s'] * len(symbols))
        cursor.execute(
            f'SELECT symbol_id, symbol FROM stock_symbol WHERE symbol IN ({placeholders})',
            tuple(symbols),
        )
        rows = cursor.fetchall() or []
        symbol_map = {str(row['symbol']).upper(): int(row['symbol_id']) for row in rows}
        missing = [symbol for symbol in symbols if symbol not in symbol_map]
        if missing:
            raise ValueError(f'以下 symbol 未在 stock_symbol 中找到: {", ".join(missing)}')
        return [symbol_map[symbol] for symbol in symbols]

    def _create_pool_mysql(self, name: str, description: str, symbols: list[str]) -> dict:
        clean_symbols = self._normalize_symbols(symbols)
        connection = self._get_mysql_connection()
        try:
            with connection.cursor() as cursor:
                cursor.execute(
                    '''
                    INSERT INTO stock_pool(owner_key, pool_name, description, is_active)
                    VALUES(%s, %s, %s, 1)
                    ''',
                    (self.owner_key, name, description),
                )
                pool_id = int(cursor.lastrowid)
                symbol_ids = self._resolve_symbol_ids_mysql(clean_symbols, cursor)
                if symbol_ids:
                    cursor.executemany(
                        '''
                        INSERT INTO stock_pool_symbol(pool_id, symbol_id, sort_order)
                        VALUES(%s, %s, %s)
                        ''',
                        [(pool_id, symbol_id, index) for index, symbol_id in enumerate(symbol_ids)],
                    )
            connection.commit()
            return self.get_pool(str(pool_id)) or {}
        except Exception:
            connection.rollback()
            raise
        finally:
            close_safely(connection)

    def _update_pool_mysql(self, pool_id: str, name: str, description: str, symbols: list[str]) -> dict | None:
        clean_symbols = self._normalize_symbols(symbols)
        connection = self._get_mysql_connection()
        try:
            with connection.cursor() as cursor:
                cursor.execute(
                    '''
                    SELECT 1
                    FROM stock_pool
                    WHERE owner_key = %s AND pool_id = %s AND is_active = 1
                    ''',
                    (self.owner_key, int(pool_id)),
                )
                if cursor.fetchone() is None:
                    return None

                cursor.execute(
                    '''
                    UPDATE stock_pool
                    SET pool_name = %s, description = %s
                    WHERE owner_key = %s AND pool_id = %s
                    ''',
                    (name, description, self.owner_key, int(pool_id)),
                )
                cursor.execute('DELETE FROM stock_pool_symbol WHERE pool_id = %s', (int(pool_id),))
                symbol_ids = self._resolve_symbol_ids_mysql(clean_symbols, cursor)
                if symbol_ids:
                    cursor.executemany(
                        '''
                        INSERT INTO stock_pool_symbol(pool_id, symbol_id, sort_order)
                        VALUES(%s, %s, %s)
                        ''',
                        [(int(pool_id), symbol_id, index) for index, symbol_id in enumerate(symbol_ids)],
                    )
            connection.commit()
            return self.get_pool(pool_id)
        except Exception:
            connection.rollback()
            raise
        finally:
            close_safely(connection)

    def _delete_pool_mysql(self, pool_id: str) -> bool:
        connection = self._get_mysql_connection()
        try:
            with connection.cursor() as cursor:
                cursor.execute('DELETE FROM stock_pool_symbol WHERE pool_id = %s', (int(pool_id),))
                affected = cursor.execute(
                    'DELETE FROM stock_pool WHERE owner_key = %s AND pool_id = %s',
                    (self.owner_key, int(pool_id)),
                )
            connection.commit()
            return affected > 0
        except Exception:
            connection.rollback()
            raise
        finally:
            close_safely(connection)

    def _list_symbols_mysql(self, keyword: str, limit: int, offset: int) -> list[dict]:
        connection = self._get_mysql_connection()
        try:
            with connection.cursor() as cursor:
                if keyword:
                    cursor.execute(
                        '''
                        SELECT symbol
                        FROM stock_symbol
                        WHERE symbol LIKE %s
                        ORDER BY symbol ASC
                        LIMIT %s OFFSET %s
                        ''',
                        (f'%{keyword}%', limit, offset),
                    )
                else:
                    cursor.execute(
                        '''
                        SELECT symbol
                        FROM stock_symbol
                        ORDER BY symbol ASC
                        LIMIT %s OFFSET %s
                        ''',
                        (limit, offset),
                    )
                rows = cursor.fetchall() or []
            return [{'symbol': str(row['symbol']).upper()} for row in rows]
        finally:
            close_safely(connection)

    def _count_symbols_mysql(self, keyword: str) -> int:
        connection = self._get_mysql_connection()
        try:
            with connection.cursor() as cursor:
                if keyword:
                    cursor.execute(
                        '''
                        SELECT COUNT(*) AS total
                        FROM stock_symbol
                        WHERE symbol LIKE %s
                        ''',
                        (f'%{keyword}%',),
                    )
                else:
                    cursor.execute('SELECT COUNT(*) AS total FROM stock_symbol')
                row = cursor.fetchone()
            return int(row['total']) if row is not None else 0
        finally:
            close_safely(connection)

    @staticmethod
    def _normalize_symbols(symbols: list[str]) -> list[str]:
        normalized: list[str] = []
        seen: set[str] = set()
        for symbol in symbols:
            clean_symbol = symbol.strip().upper()
            if not clean_symbol or clean_symbol in seen:
                continue
            seen.add(clean_symbol)
            normalized.append(clean_symbol)
        return normalized
