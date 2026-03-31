type ConfigPanelProps = {
  config: Record<string, unknown> | undefined;
};

export default function ConfigPanel({ config }: ConfigPanelProps) {
  const entries = Object.entries(config ?? {});

  return (
    <section className="table-card">
      <header className="section-title">回测参数</header>
      {entries.length > 0 ? (
        <div className="config-grid">
          {entries.map(([key, value]) => (
            <div key={key} className="config-item">
              <div className="config-key">{key}</div>
              <div className="config-value">{Array.isArray(value) ? value.join(', ') : String(value)}</div>
            </div>
          ))}
        </div>
      ) : (
        <div className="empty-state">暂无参数信息</div>
      )}
    </section>
  );
}
