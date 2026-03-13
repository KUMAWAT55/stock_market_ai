export type Signal = "BULLISH" | "BEARISH" | "HOLD" | "N/A";

export interface CandleRow {
  candle_start: string;
  candle_end: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
  is_partial?: boolean;
}

export interface SnapshotPayload {
  symbol: string;
  timeframe: string;
  generated_at: string;
  live_price: {
    symbol: string;
    last_price: number;
    price_ts: string | null;
    source: string;
  } | null;
  candles: {
    count: number;
    rows: CandleRow[];
    source: string;
  };
  signal_history: {
    count: number;
    rows: Array<{
      prediction_ts: string;
      target_ts: string;
      signal: Signal;
      confidence: number;
      prob_up: number;
      prob_down: number;
      model_name: string;
      model_version: string;
      risk_snapshot?: {
        approved_signal?: Signal;
        reason?: string;
      };
    }>;
  };
  probability_vector: {
    symbol: string;
    probabilities: Record<
      string,
      {
        signal: Signal;
        confidence: number;
        prob_up: number;
        prob_down: number;
        prediction_ts: string;
        target_ts: string;
        model_version: string;
      }
    >;
  };
  rules: {
    timeframe: string;
    rules: Record<string, number>;
  };
  engine: {
    running: boolean;
    details: {
      ws_connected?: boolean;
      loaded_model_timeframes?: string[];
      dropped_ticks?: number;
    } | null;
  };
  model_matrix: {
    rows: Array<{
      timeframe: string;
      available: boolean;
      signal: Signal | null;
      approved_signal: Signal | null;
      confidence: number | null;
      prob_up: number | null;
      prob_down: number | null;
      model_name: string | null;
      model_version: string | null;
      risk_reason: string | null;
      prediction_ts: string | null;
      target_ts: string | null;
    }>;
    consensus: {
      signal: Signal;
      score: number;
      avg_confidence: number;
    };
  };
  indicator_heatmap: {
    timeframes: string[];
    heatmap_rows: Array<{
      indicator: string;
      label: string;
      [timeframe: string]: string;
    }>;
    score_rows: Array<{
      indicator: string;
      label: string;
      [timeframe: string]: number | string | null;
    }>;
    summary: Array<{
      timeframe: string;
      composite_score: number | null;
      bias: string;
      bullish_indicators: number;
      bearish_indicators: number;
    }>;
  };
  indicator_heatmap_lag?: {
    timeframes: string[];
    heatmap_rows: Array<{
      indicator: string;
      label: string;
      [timeframe: string]: string;
    }>;
    score_rows: Array<{
      indicator: string;
      label: string;
      [timeframe: string]: number | string | null;
    }>;
    summary: Array<{
      timeframe: string;
      composite_score: number | null;
      bias: string;
      bullish_indicators: number;
      bearish_indicators: number;
    }>;
  };
  indicator_heatmap_lead?: {
    timeframes: string[];
    heatmap_rows: Array<{
      indicator: string;
      label: string;
      [timeframe: string]: string;
    }>;
    score_rows: Array<{
      indicator: string;
      label: string;
      [timeframe: string]: number | string | null;
    }>;
    summary: Array<{
      timeframe: string;
      composite_score: number | null;
      bias: string;
      bullish_indicators: number;
      bearish_indicators: number;
    }>;
  };
  model_backtest: BacktestPayload;
  simulated_backtest: {
    model_name: string;
    model_version: string;
    run_ts: string;
    metrics: Record<string, number | string>;
    requested_symbol: string;
    source_symbol: string;
    fallback_used: boolean;
  } | null;
}

export interface BacktestPayload {
  symbol: string;
  timeframe: string;
  trade_count: number;
  win_rate: number;
  avg_return: number;
  total_return: number;
  max_drawdown: number;
  sharpe_like: number;
  profit_factor: number | null;
}

export interface StrategyBacktestPayload extends BacktestPayload {
  strategy: string;
  strategy_note?: string;
  latest_signal?: string;
}

export interface ScannerPayload {
  timeframe: string;
  signal: string;
  min_confidence: number;
  count: number;
  rows: Array<{
    symbol: string;
    timeframe: string;
    signal: Signal;
    approved_signal: Signal;
    confidence: number;
    prob_up: number;
    prob_down: number;
    model_name: string;
    model_version: string;
    prediction_ts: string;
    target_ts: string;
    risk_reason: string | null;
  }>;
}

export interface AuthUser {
  id: number;
  username: string;
  email: string;
  full_name: string;
}

export interface AuthResponse {
  token: string;
  user: AuthUser;
}
