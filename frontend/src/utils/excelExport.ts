import * as XLSX from 'xlsx';

export function downloadExcel(rows: Record<string, unknown>[], sheetName: string, filename: string): void {
  if (rows.length === 0) {
    return;
  }
  const safeSheet = sheetName.slice(0, 31) || 'Sheet1';
  const ws = XLSX.utils.json_to_sheet(rows);
  const wb = XLSX.utils.book_new();
  XLSX.utils.book_append_sheet(wb, ws, safeSheet);
  const name = filename.endsWith('.xlsx') ? filename : `${filename}.xlsx`;
  XLSX.writeFile(wb, name);
}
