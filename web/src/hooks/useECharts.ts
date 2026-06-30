import { useRef, useEffect } from 'react'
import * as echarts from 'echarts'

export function useECharts() {
  const chartRef = useRef<echarts.ECharts | null>(null)
  const domRef = useRef<HTMLDivElement | null>(null)

  const initChart = (dom: HTMLDivElement | null) => {
    if (!dom) return
    disposeChart()
    domRef.current = dom
    chartRef.current = echarts.init(dom, 'dark')
    return chartRef.current
  }

  const setOption = (option: echarts.EChartsOption) => {
    chartRef.current?.setOption(option)
  }

  const disposeChart = () => {
    chartRef.current?.dispose()
    chartRef.current = null
    domRef.current = null
  }

  const getChart = () => chartRef.current

  // auto resize on window resize
  useEffect(() => {
    const handler = () => chartRef.current?.resize()
    window.addEventListener('resize', handler)
    return () => {
      window.removeEventListener('resize', handler)
      disposeChart()
    }
  }, [])

  return { initChart, setOption, disposeChart, getChart, chartRef, domRef }
}
