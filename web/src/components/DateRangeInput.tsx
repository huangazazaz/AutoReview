interface DateRangeInputProps {
  startDate: string
  endDate: string
  onChange: (start: string, end: string) => void
}

export default function DateRangeInput({ startDate, endDate, onChange }: DateRangeInputProps) {
  return (
    <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
      <input
        type="date"
        className="form-input date-input"
        value={startDate}
        onChange={e => onChange(e.target.value, endDate)}
        style={{ flex: 1 }}
      />
      <span style={{ color: 'var(--text-muted)', fontSize: 12 }}>至</span>
      <input
        type="date"
        className="form-input date-input"
        value={endDate}
        onChange={e => onChange(startDate, e.target.value)}
        style={{ flex: 1 }}
      />
    </div>
  )
}
