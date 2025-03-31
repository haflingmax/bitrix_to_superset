import React from 'react';
import * as d3 from 'd3';
import { ChartProps } from '@superset-ui/core';

const D3TreeChart: React.FC<ChartProps> = (props) => {
  const { queriesData, width, height } = props;
  const rootRef = React.useRef<SVGSVGElement>(null);
  const data = queriesData?.[0]?.data || [];

  React.useEffect(() => {
    if (!rootRef.current || !data || data.length === 0) return;

    const svg = d3.select(rootRef.current)
      .attr('width', width)
      .attr('height', height);
    svg.selectAll('*').remove();

    const stratify = d3.stratify()
      .id((d: any) => String(d.id))
      .parentId((d: any) => (d.parent_id ? String(d.parent_id) : null));
    const treeData = stratify(data);

    const treeLayout = d3.tree().size([height - 50, width - 50]);
    const rootNode = treeLayout(treeData);

    const g = svg.append('g').attr('transform', 'translate(25, 25)');

    g.selectAll('.link')
      .data(rootNode.links())
      .enter()
      .append('path')
      .attr('class', 'link')
      .attr('d', (d: any) => {
        const link = d3.linkHorizontal()
          .x((node: any) => node.y)
          .y((node: any) => node.x);
        return link(d);
      })
      .style('fill', 'none')
      .style('stroke', '#ccc')
      .style('stroke-width', '2px');

    const node = g.selectAll('.node')
      .data(rootNode.descendants())
      .enter()
      .append('g')
      .attr('class', 'node')
      .attr('transform', (d: any) => `translate(${d.y},${d.x})`);

    node.append('circle')
      .attr('r', 5)
      .style('fill', '#69b3a2')
      .style('stroke', '#fff')
      .style('stroke-width', '1.5px');

    node.append('text')
      .attr('dy', '.35em')
      .attr('x', (d: any) => (d.children ? -10 : 10))
      .attr('text-anchor', (d: any) => (d.children ? 'end' : 'start'))
      .text((d: any) => d.data.title || d.data.id)
      .style('font-size', '12px');
  }, [data, height, width]);

  return <svg ref={rootRef} />;
};

export default D3TreeChart;