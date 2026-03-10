/// <reference types="vite/client" />

declare module "react-plotly.js" {
  import * as React from "react";

  export interface PlotProps {
    data?: Record<string, unknown>[];
    layout?: Record<string, unknown>;
    config?: Record<string, unknown>;
    style?: React.CSSProperties;
    className?: string;
    useResizeHandler?: boolean;
  }

  const Plot: React.ComponentType<PlotProps>;
  export default Plot;
}
