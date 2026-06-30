/**
 * 格式化工具函数 — 与原前端保持一致，使用 zh-CN locale
 */

export function escapeHtml(str: string | null | undefined): string {
  if (str == null) return ''
  const div = document.createElement('div')
  div.textContent = String(str)
  return div.innerHTML
}

export function formatNumber(value: number | null | undefined, decimals = 2): string {
  if (value == null || isNaN(value)) return '—'
  return Number(value).toLocaleString('zh-CN', {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  })
}

export function formatAmount(value: number | null | undefined): string {
  if (value == null || isNaN(value)) return '—'
  const abs = Math.abs(value)
  if (abs >= 1e8) return '¥' + (value / 1e8).toFixed(2) + ' 亿'
  if (abs >= 1e4) return '¥' + (value / 1e4).toFixed(2) + ' 万'
  return '¥' + Number(value).toLocaleString('zh-CN', {
    minimumFractionDigits: 0,
    maximumFractionDigits: 0,
  })
}

export function formatVolume(value: number | null | undefined): string {
  if (value == null || isNaN(value)) return '—'
  if (value >= 1e8) return (value / 1e8).toFixed(2) + ' 亿'
  if (value >= 1e4) return (value / 1e4).toFixed(2) + ' 万'
  return Number(value).toLocaleString('zh-CN')
}

export function formatPct(value: number | null | undefined): string {
  if (value == null || isNaN(value)) return '—'
  return (value >= 0 ? '+' : '') + value.toFixed(2) + '%'
}

export function formatMoney(value: number | null | undefined): string {
  if (value == null || isNaN(value)) return '—'
  return Number(value).toLocaleString('zh-CN', {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })
}
