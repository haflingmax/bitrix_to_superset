import { ChartPlugin, ChartMetadata } from '@superset-ui/core';
import transformProps from './plugin/transformProps';
import thumbnail from '../images/thumbnail.png';

export default class SupersetPluginChartD3Tree extends ChartPlugin {
  constructor() {
    super({
      metadata: {
        name: 'Tree Table',
        description: 'A tree chart built with D3.js',
        thumbnail,
        credits: ['haflingmax'],
        category: 'Hierarchy',
        tags: ['D3', 'Tree'],
        behaviors: [],
        datasourceCount: 1,
        canBeAnnotationTypesLookup: false,
        show: true,
        supportedAnnotationTypes: [],
        useLegacyApi: false,
        isCertified: false,
        cacheTimeout: 0,
        supportsCostEstimate: false,
        enableNoResults: true,
        deprecated: false,
        exampleGallery: [],
        canBeAnnotationType: false,
      } as unknown as ChartMetadata, // Приведение через unknown
      loadChart: () => import('./D3TreeChart'),
      transformProps,
    });
  }
}