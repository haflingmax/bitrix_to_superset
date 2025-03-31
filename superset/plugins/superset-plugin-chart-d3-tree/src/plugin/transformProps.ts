import { ChartProps } from '@superset-ui/core';

export default function transformProps(chartProps: ChartProps) {
  return {
    ...chartProps,
  };
}