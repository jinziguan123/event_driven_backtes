from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class MysqlConfig:
    host: str
    port: int
    user: str
    password: str
    database: str
    charset: str = 'utf8mb4'


@dataclass(frozen=True)
class ClickHouseConfig:
    host: str
    port: int
    user: str
    password: str
    database: str
    secure: bool = False


def _env(name: str, fallback_name: str | None = None, default: str = '') -> str:
    value = os.environ.get(name)
    if value is not None:
        return value
    if fallback_name:
        fallback_value = os.environ.get(fallback_name)
        if fallback_value is not None:
            return fallback_value
    return default


def _to_bool(value: str | None, default: bool = False) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {'1', 'true', 'yes', 'on'}


def build_mysql_config_from_env() -> MysqlConfig:
    return MysqlConfig(
        host=_env('EVENT_BT_MYSQL_HOST', 'MYSQL_HOST', '172.30.26.12'),
        port=int(_env('EVENT_BT_MYSQL_PORT', 'MYSQL_PORT', '3306')),
        user=_env('EVENT_BT_MYSQL_USER', 'MYSQL_USER', 'root'),
        password=_env('EVENT_BT_MYSQL_PASSWORD', 'MYSQL_PASSWORD', 'Jinziguan123'),
        database=_env('EVENT_BT_MYSQL_DATABASE', 'MYSQL_DATABASE', 'quant_data'),
        charset=_env('EVENT_BT_MYSQL_CHARSET', 'MYSQL_CHARSET', 'utf8mb4'),
    )


def build_clickhouse_config_from_env() -> ClickHouseConfig:
    return ClickHouseConfig(
        host=_env('EVENT_BT_CLICKHOUSE_HOST', 'CLICKHOUSE_HOST', '172.30.26.12'),
        port=int(_env('EVENT_BT_CLICKHOUSE_PORT', 'CLICKHOUSE_PORT', '8123')),
        user=_env('EVENT_BT_CLICKHOUSE_USER', 'CLICKHOUSE_USER', 'quant'),
        password=_env('EVENT_BT_CLICKHOUSE_PASSWORD', 'CLICKHOUSE_PASSWORD', 'Jinziguan123'),
        database=_env('EVENT_BT_CLICKHOUSE_DATABASE', 'CLICKHOUSE_DATABASE', 'quant_data'),
        secure=_to_bool(_env('EVENT_BT_CLICKHOUSE_SECURE', 'CLICKHOUSE_SECURE', 'false')),
    )


def _import_pymysql():
    try:
        import pymysql
    except ModuleNotFoundError as exc:
        raise RuntimeError('缺少 PyMySQL 依赖，请先安装 requirements.txt') from exc
    return pymysql


def _import_clickhouse_connect():
    try:
        import clickhouse_connect
    except ModuleNotFoundError as exc:
        raise RuntimeError('缺少 clickhouse-connect 依赖，请先安装 requirements.txt') from exc
    return clickhouse_connect


def connect_mysql(config: MysqlConfig | None = None):
    pymysql = _import_pymysql()
    cfg = config or build_mysql_config_from_env()
    return pymysql.connect(
        host=cfg.host,
        port=cfg.port,
        user=cfg.user,
        password=cfg.password,
        database=cfg.database,
        charset=cfg.charset,
        cursorclass=pymysql.cursors.DictCursor,
        autocommit=False,
    )


def connect_clickhouse(config: ClickHouseConfig | None = None):
    clickhouse_connect = _import_clickhouse_connect()
    cfg = config or build_clickhouse_config_from_env()
    return clickhouse_connect.get_client(
        host=cfg.host,
        port=cfg.port,
        username=cfg.user,
        password=cfg.password,
        database=cfg.database,
        secure=cfg.secure,
    )


def close_safely(connection_or_client) -> None:
    close_method = getattr(connection_or_client, 'close', None)
    if callable(close_method):
        close_method()
