const statusMap: Record<string, string> = {
  RUNNING: 'running',
  CANCELING: 'canceling',
  CANCELED: 'canceled',
  SUCCESS: 'success',
  FAILED: 'failed',
};

const statusLabelZh: Record<string, string> = {
  RUNNING: '运行中',
  CANCELING: '中断中',
  CANCELED: '已中断',
  SUCCESS: '成功',
  FAILED: '失败',
};

type StatusBadgeProps = {
  status: string;
};

export default function StatusBadge({ status }: StatusBadgeProps) {
  const variant = statusMap[status] ?? 'default';
  const label = statusLabelZh[status] ?? status;
  return <span className={`status-badge ${variant}`}>{label}</span>;
}
