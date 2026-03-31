import type { SummaryMetric } from '../types';

type SummaryCardsProps = {
  metrics: SummaryMetric[];
};

export default function SummaryCards({ metrics }: SummaryCardsProps) {
  return (
    <section className="summary-grid">
      {metrics.map((metric) => (
        <article key={metric.label} className="summary-card">
          <div className="summary-label">{metric.label}</div>
          <div className="summary-value">{metric.value}</div>
        </article>
      ))}
    </section>
  );
}
