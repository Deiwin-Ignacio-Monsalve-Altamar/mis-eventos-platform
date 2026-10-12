/** Render a small labelled chart from API-provided aggregate values. */

/** Show each series value as a proportional accessible bar. */
export default function ProfileBarChart({ title, label, items }) {
  const maximum = Math.max(1, ...items.map((item) => item.value))
  return (
    <section aria-label={label} className="profile-chart">
      <h3>{title}</h3>
      {items.map((item) => {
        const percentage = item.value === 0 ? 0 : Math.max(2, (item.value / maximum) * 100)
        return (
            <div className="profile-chart-row" key={item.key ?? item.label}>
            <span>{item.label}</span>
            <div aria-label={`${item.label}: ${item.value}`} aria-valuemax={maximum} aria-valuemin="0" aria-valuenow={item.value} className="profile-chart-track" role="progressbar">
              <span style={{ width: `${percentage}%` }} />
            </div>
            <strong>{item.value}</strong>
          </div>
        )
      })}
    </section>
  )
}
