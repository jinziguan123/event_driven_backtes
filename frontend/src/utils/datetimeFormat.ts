/** 统一展示为 yyyy-MM-dd HH:mm:ss */
export function formatDisplayDateTime(value?: string | null): string {
  if (value == null || value === '') {
    return '--';
  }
  const s = String(value).trim();
  const m = s.match(/^(\d{4}-\d{2}-\d{2})[T ](\d{2}:\d{2}:\d{2})/);
  if (m) {
    return `${m[1]} ${m[2]}`;
  }
  const dOnly = s.match(/^(\d{4}-\d{2}-\d{2})$/);
  if (dOnly) {
    return `${dOnly[1]} 00:00:00`;
  }
  return s;
}

/** 与展示一致的时间键，用于对齐、排序 */
export function normalizeTimestampKey(value: string): string {
  return formatDisplayDateTime(value);
}

export function timestampsMatch(a: string | undefined | null, b: string | undefined | null): boolean {
  if (a == null || b == null || a === '' || b === '') {
    return false;
  }
  return normalizeTimestampKey(a) === normalizeTimestampKey(b);
}
