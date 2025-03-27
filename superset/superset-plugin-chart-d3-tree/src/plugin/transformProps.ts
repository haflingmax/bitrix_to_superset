import { ChartProps } from '@superset-ui/core';
import { SupersetPluginChartD3TreeProps } from '../types';

export default function transformProps(chartProps: ChartProps): SupersetPluginChartD3TreeProps {
  const { width, height, queriesData } = chartProps;
  const data = queriesData[0].data || [];

  return {
    data,
    height,
    width,
  };
}