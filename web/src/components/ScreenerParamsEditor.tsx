import { useState } from 'react'
import type { ScreenerInfo } from '@/types'

interface Props {
  screener: ScreenerInfo | undefined
  /** Current edit values keyed by param name */
  editParams: Record<string, string>
  onChange: (key: string, value: string) => void
}

const SIMPLE_TYPES = new Set(['int', 'float', 'str', 'bool'])

export default function ScreenerParamsEditor({ screener, editParams, onChange }: Props) {
  const [expanded, setExpanded] = useState(false)

  if (!screener?.param_schema || Object.keys(screener.param_schema).length === 0) {
    return null
  }

  const schema = screener.param_schema
  const entries = Object.entries(schema)
  const simpleEntries = entries.filter(([, info]) => SIMPLE_TYPES.has(info.type || 'str'))
  const complexEntries = entries.filter(([, info]) => !SIMPLE_TYPES.has(info.type || 'str'))

  const summary = entries.slice(0, 5).map(([k]) => {
    const v = editParams[k] !== undefined ? editParams[k] : '\u2014'
    return `${k}=${v}`
  }).join(', ') + (entries.length > 5 ? ` +${entries.length - 5}` : '')

  return (
    <div className="params-section" style={{ marginTop: 16 }}>
      <button
        type="button"
        className="params-toggle"
        onClick={() => setExpanded(!expanded)}
        aria-expanded={expanded}
      >
        <span className="toggle-icon">{expanded ? '\u25BC' : '\u25B6'}</span> 选股器参数
        <span className="params-summary">{summary}</span>
      </button>
      {expanded && (
        <div className="params-body">
          <div className="param-grid">
            {simpleEntries.map(([key, info]) => {
              const inputType = info.type === 'int' || info.type === 'float' ? 'number' : 'text'
              const step = info.type === 'float' ? '0.01' : info.type === 'int' ? '1' : undefined
              return (
                <div key={key} className="param-item">
                  <label
                    className="param-label"
                    title={`${key}${info.default !== undefined ? ' \u00B7 默认: ' + JSON.stringify(info.default) : ''}`}
                  >
                    {key}
                  </label>
                  <input
                    type={inputType}
                    className="form-input"
                    value={editParams[key] ?? ''}
                    placeholder={info.default !== undefined ? String(info.default) : ''}
                    step={step as number | undefined}
                    onChange={e => onChange(key, e.target.value)}
                  />
                </div>
              )
            })}
          </div>
          {complexEntries.map(([key, info]) => (
            <div key={key} className="param-item param-item-wide">
              <label className="param-label">
                {key} <span className="param-type-tag">{info.type}</span>
              </label>
              <textarea
                className="form-input"
                rows={2}
                value={editParams[key] ?? ''}
                placeholder={info.default !== undefined ? JSON.stringify(info.default) : ''}
                onChange={e => onChange(key, e.target.value)}
              />
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
