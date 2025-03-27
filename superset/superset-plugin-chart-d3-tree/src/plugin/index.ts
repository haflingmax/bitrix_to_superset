import { ChartPlugin } from '@superset-ui/core';
import transformProps from './transformProps';
import SupersetPluginChartD3Tree from '../SupersetPluginChartD3Tree';

export default class SupersetPluginChartD3TreePlugin extends ChartPlugin {
  constructor() {
    super({
      loadChart: () => import('../SupersetPluginChartD3Tree'),
      metadata: {
        name: 'D3 Tree Chart',
        description: 'A tree chart for hierarchical data using D3.js',
        key: 'd3-tree',
      },
      transformProps,
    });
  }
}