/** Render labelled metrics in the shared profile card style. */

/** Present a compact, accessible group of verified values. */
export default function ProfileMetricGrid({ label, metrics }) {
  return (
    <dl aria-label={label} className="activity-metrics">
      {metrics.map(({ label: metricLabel, value }) => (
        <div key={metricLabel}><dt>{metricLabel}</dt><dd>{value}</dd></div>
      ))}
    </dl>
  )
}
