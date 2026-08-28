// ECharts 按需引入: 全量包 ~1MB, 只用 bar/graph 两种图, 按需后省 ~70%
import * as echarts from "echarts/core";
import { BarChart, GraphChart } from "echarts/charts";
import { GridComponent, TooltipComponent } from "echarts/components";
import { CanvasRenderer } from "echarts/renderers";

echarts.use([BarChart, GraphChart, GridComponent, TooltipComponent, CanvasRenderer]);

export { echarts };
export type { ECharts } from "echarts/core";
