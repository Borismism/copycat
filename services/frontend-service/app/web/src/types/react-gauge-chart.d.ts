declare module 'react-gauge-chart' {
  import { FC } from 'react'

  export interface GaugeChartProps {
    id?: string
    nrOfLevels?: number
    percent?: number
    colors?: string[]
    arcWidth?: number
    hideText?: boolean
    textColor?: string
    needleColor?: string
    needleBaseColor?: string
    animDelay?: number
  }

  const GaugeChart: FC<GaugeChartProps>
  export default GaugeChart
}
