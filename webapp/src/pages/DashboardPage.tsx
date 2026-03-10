import { useCallback, useEffect, useMemo, useState } from "react";
import Plot from "react-plotly.js";

import { getScanner, getSnapshot, getStrategyBacktest, getSymbols } from "../api";
import type { ScannerPayload, SnapshotPayload, StrategyBacktestPayload } from "../types";

const TIMEFRAMES = ["1m", "5m", "15m", "1h", "1d"];
const STRATEGIES = [
  { value: "ema_trend", label: "EMA Trend" },
  { value: "rsi_reversal", label: "RSI Reversal" },
  { value: "macd_impulse", label: "MACD Impulse" },
];

function formatPercent(value?: number | null): string {
  if (value === null || value === undefined || Number.isNaN(value)) return "N/A";
  return `${(value * 100).toFixed(2)}%`;
}

function formatTs(value?: string | null): string {
  if (!value) return "N/A";
  const dt = new Date(value);
  if (Number.isNaN(dt.getTime())) return "N/A";
  return dt.toLocaleString("en-IN", { hour12: false });
}

function ema(values: number[], period: number): number[] {
  if (!values.length) return [];
  const k = 2 / (period + 1);
  const out: number[] = [values[0]];
  for (let i = 1; i < values.length; i += 1) {
    out.push(values[i] * k + out[i - 1] * (1 - k));
  }
  return out;
}

function heatClass(bias: string): string {
  if (bias === "bullish") return "heat-cell heat-bull";
  if (bias === "bearish") return "heat-cell heat-bear";
  if (bias === "neutral") return "heat-cell heat-neutral";
  return "heat-cell heat-empty";
}

export default function DashboardPage() {
  const [symbols, setSymbols] = useState<string[]>([]);
  const [symbol, setSymbol] = useState<string>("RELIANCE");
  const [timeframe, setTimeframe] = useState<string>("15m");
  const [refreshSec, setRefreshSec] = useState<number>(5);
  const [candleLimit, setCandleLimit] = useState<number>(320);
  const [historyLimit, setHistoryLimit] = useState<number>(220);
  const [strategy, setStrategy] = useState<string>("ema_trend");
  const [scannerSignal, setScannerSignal] = useState<string>("ALL");
  const [scannerMinConfidence, setScannerMinConfidence] = useState<number>(0.6);
  const [scannerTimeframe, setScannerTimeframe] = useState<string>("5m");
  const [snapshot, setSnapshot] = useState<SnapshotPayload | null>(null);
  const [strategyBacktest, setStrategyBacktest] = useState<StrategyBacktestPayload | null>(null);
  const [scanner, setScanner] = useState<ScannerPayload | null>(null);
  const [loading, setLoading] = useState<boolean>(false);
  const [error, setError] = useState<string>("");

  const loadSnapshot = useCallback(async () => {
    if (!symbol) return;
    setLoading(true);
    try {
      const snapshotPayload = await getSnapshot({
        symbol,
        timeframe,
        candleLimit,
        historyLimit,
      });
      setSnapshot(snapshotPayload);
    } catch (err) {
      const message = err instanceof Error ? err.message : String(err);
      setError(message);
    } finally {
      setLoading(false);
    }
  }, [symbol, timeframe, candleLimit, historyLimit]);

  const loadSecondaryAnalytics = useCallback(async () => {
    if (!symbol) return;
    try {
      const [strategyPayload, scannerPayload] = await Promise.all([
        getStrategyBacktest({
          symbol,
          timeframe,
          strategy,
          candleLimit: Math.max(400, candleLimit * 2),
          costBps: 2,
        }),
        getScanner({
          timeframe: scannerTimeframe,
          signal: scannerSignal,
          minConfidence: scannerMinConfidence,
          limit: 50,
        }),
      ]);
      setStrategyBacktest(strategyPayload);
      setScanner(scannerPayload);
    } catch (err) {
      const message = err instanceof Error ? err.message : String(err);
      setError(message);
    }
  }, [symbol, timeframe, strategy, candleLimit, scannerTimeframe, scannerSignal, scannerMinConfidence]);

  const loadAll = useCallback(async () => {
    setError("");
    await Promise.all([loadSnapshot(), loadSecondaryAnalytics()]);
  }, [loadSnapshot, loadSecondaryAnalytics]);

  useEffect(() => {
    let active = true;
    getSymbols()
      .then((rows) => {
        if (!active) return;
        setSymbols(rows);
        if (rows.length > 0) {
          setSymbol((current) => (rows.includes(current) ? current : rows[0]));
        }
      })
      .catch((err) => {
        if (!active) return;
        const message = err instanceof Error ? err.message : String(err);
        setError(message);
      });
    return () => {
      active = false;
    };
  }, []);

  useEffect(() => {
    void loadSnapshot();
  }, [loadSnapshot]);

  useEffect(() => {
    void loadSecondaryAnalytics();
  }, [loadSecondaryAnalytics]);

  useEffect(() => {
    if (refreshSec <= 0) return undefined;
    const timer = window.setInterval(() => {
      void loadSnapshot();
    }, refreshSec * 1000);
    return () => window.clearInterval(timer);
  }, [refreshSec, loadSnapshot]);

  useEffect(() => {
    const intervalSec = Math.max(15, refreshSec * 4);
    const timer = window.setInterval(() => {
      void loadSecondaryAnalytics();
    }, intervalSec * 1000);
    return () => window.clearInterval(timer);
  }, [refreshSec, loadSecondaryAnalytics]);

  const chartData = useMemo(() => {
    const candles = snapshot?.candles?.rows ?? [];
    if (!candles.length) return null;
    const x = candles.map((row) => row.candle_start);
    const open = candles.map((row) => row.open);
    const high = candles.map((row) => row.high);
    const low = candles.map((row) => row.low);
    const close = candles.map((row) => row.close);
    const ema12 = ema(close, 12);
    const ema26 = ema(close, 26);
    return { x, open, high, low, close, ema12, ema26 };
  }, [snapshot]);
  const chartLayout = useMemo(
    () => ({
      margin: { l: 30, r: 20, t: 10, b: 30 },
      plot_bgcolor: "#0f1219",
      paper_bgcolor: "#0f1219",
      xaxis: { rangeslider: { visible: false }, color: "#b4bac8" },
      yaxis: { color: "#b4bac8", fixedrange: false },
      legend: { orientation: "h", y: 1.12, x: 0 },
      // Keep user zoom/pan when candles refresh for same symbol+timeframe.
      uirevision: `${symbol}:${timeframe}`,
    }),
    [symbol, timeframe],
  );

  const latestSignal = snapshot?.signal_history?.rows?.[0] ?? null;
  const lastPrice = snapshot?.live_price?.last_price ?? null;
  const ruleProfile = snapshot?.rules?.rules ?? {};

  return (
    <div className="app-shell">
      <header className="hero">
        <div>
          <p className="kicker">Intraday Quant Terminal</p>
          <h1>TradeIQ React Desk</h1>
          <p className="subtitle">Live market data, timeframe model matrix, indicator heatmap, scanner, and strategy lab.</p>
        </div>
        <div className="hero-right">
          <button className="btn-primary" onClick={() => void loadAll()} disabled={loading}>
            {loading ? "Refreshing..." : "Refresh Now"}
          </button>
          <p className="timestamp">Last update: {snapshot ? formatTs(snapshot.generated_at) : "N/A"}</p>
        </div>
      </header>

      <section className="controls">
        <label>
          Symbol
          <select value={symbol} onChange={(event) => setSymbol(event.target.value)}>
            {(symbols.length ? symbols : ["RELIANCE"]).map((item) => (
              <option key={item} value={item}>
                {item}
              </option>
            ))}
          </select>
        </label>
        <label>
          Timeframe
          <select value={timeframe} onChange={(event) => setTimeframe(event.target.value)}>
            {TIMEFRAMES.map((item) => (
              <option key={item} value={item}>
                {item}
              </option>
            ))}
          </select>
        </label>
        <label>
          Auto Refresh (sec)
          <input
            type="number"
            min={0}
            max={60}
            value={refreshSec}
            onChange={(event) => setRefreshSec(Number(event.target.value))}
          />
        </label>
        <label>
          Candles
          <input
            type="number"
            min={80}
            max={1000}
            value={candleLimit}
            onChange={(event) => setCandleLimit(Number(event.target.value))}
          />
        </label>
        <label>
          History Rows
          <input
            type="number"
            min={50}
            max={1000}
            value={historyLimit}
            onChange={(event) => setHistoryLimit(Number(event.target.value))}
          />
        </label>
      </section>

      {error && <div className="error-banner">{error}</div>}

      <section className="metric-grid">
        <article className="metric-card">
          <p>Live Price</p>
          <h2>{lastPrice ? `₹ ${lastPrice.toFixed(2)}` : "N/A"}</h2>
          <small>{snapshot?.live_price?.source ?? "No source"}</small>
        </article>
        <article className="metric-card">
          <p>Primary Signal</p>
          <h2>{latestSignal?.risk_snapshot?.approved_signal ?? latestSignal?.signal ?? "N/A"}</h2>
          <small>{latestSignal ? `Confidence ${formatPercent(latestSignal.confidence)}` : "No prediction yet"}</small>
        </article>
        <article className="metric-card">
          <p>Matrix Consensus</p>
          <h2>{snapshot?.model_matrix?.consensus?.signal ?? "N/A"}</h2>
          <small>{formatPercent(snapshot?.model_matrix?.consensus?.avg_confidence)}</small>
        </article>
        <article className="metric-card">
          <p>Engine Stream</p>
          <h2>{snapshot?.engine?.details?.ws_connected ? "Connected" : "Disconnected"}</h2>
          <small>Dropped ticks: {snapshot?.engine?.details?.dropped_ticks ?? 0}</small>
        </article>
      </section>

      <section className="layout-main">
        <article className="panel">
          <div className="panel-head">
            <h3>{symbol} {timeframe} Live Candles</h3>
            <span>{snapshot?.candles?.source ?? "N/A"}</span>
          </div>
          <div className="chart-wrap">
            {chartData ? (
              <Plot
                data={[
                  {
                    type: "candlestick",
                    x: chartData.x,
                    open: chartData.open,
                    high: chartData.high,
                    low: chartData.low,
                    close: chartData.close,
                    name: "OHLC",
                    increasing: { line: { color: "#32c27a" } },
                    decreasing: { line: { color: "#ed5757" } },
                  },
                  {
                    type: "scatter",
                    mode: "lines",
                    x: chartData.x,
                    y: chartData.ema12,
                    name: "EMA 12",
                    line: { color: "#f8b74c", width: 1.4 },
                  },
                  {
                    type: "scatter",
                    mode: "lines",
                    x: chartData.x,
                    y: chartData.ema26,
                    name: "EMA 26",
                    line: { color: "#4c8bf8", width: 1.4 },
                  },
                ]}
                layout={chartLayout}
                config={{ responsive: true, displaylogo: false }}
                style={{ width: "100%", height: "100%" }}
                useResizeHandler
              />
            ) : (
              <div className="empty-state">No candle data available.</div>
            )}
          </div>
        </article>

        <article className="panel">
          <div className="panel-head">
            <h3>Timeframe Rules</h3>
          </div>
          <div className="kv-list">
            <div><span>Buy Threshold</span><b>{formatPercent(ruleProfile.signal_buy_threshold)}</b></div>
            <div><span>Sell Threshold</span><b>{formatPercent(ruleProfile.signal_sell_threshold)}</b></div>
            <div><span>Min Confidence</span><b>{formatPercent(ruleProfile.min_confidence)}</b></div>
            <div><span>Cooldown</span><b>{Math.round(ruleProfile.cooldown_seconds ?? 0)} sec</b></div>
            <div><span>Stop Loss</span><b>{formatPercent(ruleProfile.stop_loss_pct)}</b></div>
            <div><span>Drawdown Cap</span><b>{formatPercent(ruleProfile.max_drawdown_pct)}</b></div>
          </div>

          <div className="divider" />
          <h4>Model Backtest</h4>
          <div className="kv-list">
            <div><span>Trades</span><b>{snapshot?.model_backtest?.trade_count ?? 0}</b></div>
            <div><span>Win Rate</span><b>{formatPercent(snapshot?.model_backtest?.win_rate)}</b></div>
            <div><span>Total Return</span><b>{formatPercent(snapshot?.model_backtest?.total_return)}</b></div>
            <div><span>Max DD</span><b>{formatPercent(snapshot?.model_backtest?.max_drawdown)}</b></div>
            <div><span>Sharpe-like</span><b>{(snapshot?.model_backtest?.sharpe_like ?? 0).toFixed(2)}</b></div>
          </div>
        </article>
      </section>

      <section className="panel">
        <div className="panel-head">
          <h3>Model Matrix Across Timeframes</h3>
          <span>Consensus: {snapshot?.model_matrix?.consensus?.signal ?? "N/A"}</span>
        </div>
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>TF</th>
                <th>Signal</th>
                <th>Approved</th>
                <th>Confidence</th>
                <th>Prob Up</th>
                <th>Model</th>
                <th>Version</th>
                <th>Risk Note</th>
              </tr>
            </thead>
            <tbody>
              {(snapshot?.model_matrix?.rows ?? []).map((row) => (
                <tr key={row.timeframe}>
                  <td>{row.timeframe}</td>
                  <td>{row.signal ?? "N/A"}</td>
                  <td>{row.approved_signal ?? "N/A"}</td>
                  <td>{formatPercent(row.confidence)}</td>
                  <td>{formatPercent(row.prob_up)}</td>
                  <td>{row.model_name ?? "N/A"}</td>
                  <td>{row.model_version ?? "N/A"}</td>
                  <td>{row.risk_reason ?? "-"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      <section className="panel">
        <div className="panel-head">
          <h3>Indicator Heatmap</h3>
          <span>Bullish/Bearish map for each timeframe</span>
        </div>
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Indicator</th>
                {(snapshot?.indicator_heatmap?.timeframes ?? []).map((tf) => (
                  <th key={tf}>{tf}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {(snapshot?.indicator_heatmap?.heatmap_rows ?? []).map((row) => (
                <tr key={row.indicator}>
                  <td>{row.label}</td>
                  {(snapshot?.indicator_heatmap?.timeframes ?? []).map((tf) => (
                    <td key={`${row.indicator}-${tf}`} className={heatClass(String(row[tf] ?? "no_data"))}>
                      {String(row[tf] ?? "no_data")}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      <section className="layout-split">
        <article className="panel">
          <div className="panel-head">
            <h3>Strategy Lab (Streak-style)</h3>
          </div>
          <div className="inline-controls">
            <label>
              Strategy
              <select value={strategy} onChange={(event) => setStrategy(event.target.value)}>
                {STRATEGIES.map((item) => (
                  <option key={item.value} value={item.value}>
                    {item.label}
                  </option>
                ))}
              </select>
            </label>
          </div>
          <div className="kv-list">
            <div><span>Latest Signal</span><b>{strategyBacktest?.latest_signal ?? "N/A"}</b></div>
            <div><span>Trades</span><b>{strategyBacktest?.trade_count ?? 0}</b></div>
            <div><span>Win Rate</span><b>{formatPercent(strategyBacktest?.win_rate)}</b></div>
            <div><span>Total Return</span><b>{formatPercent(strategyBacktest?.total_return)}</b></div>
            <div><span>Max DD</span><b>{formatPercent(strategyBacktest?.max_drawdown)}</b></div>
            <div><span>Sharpe-like</span><b>{(strategyBacktest?.sharpe_like ?? 0).toFixed(2)}</b></div>
          </div>
          <p className="note">{strategyBacktest?.strategy_note ?? ""}</p>
        </article>

        <article className="panel">
          <div className="panel-head">
            <h3>Intraday Scanner</h3>
            <span>{scanner?.count ?? 0} candidates</span>
          </div>
          <div className="inline-controls three-col">
            <label>
              TF
              <select value={scannerTimeframe} onChange={(event) => setScannerTimeframe(event.target.value)}>
                {TIMEFRAMES.map((item) => (
                  <option key={item} value={item}>
                    {item}
                  </option>
                ))}
              </select>
            </label>
            <label>
              Signal
              <select value={scannerSignal} onChange={(event) => setScannerSignal(event.target.value)}>
                {["ALL", "BUY", "SELL", "HOLD"].map((item) => (
                  <option key={item} value={item}>
                    {item}
                  </option>
                ))}
              </select>
            </label>
            <label>
              Min Confidence
              <input
                type="number"
                min={0}
                max={1}
                step={0.01}
                value={scannerMinConfidence}
                onChange={(event) => setScannerMinConfidence(Number(event.target.value))}
              />
            </label>
          </div>
          <div className="table-wrap compact">
            <table>
              <thead>
                <tr>
                  <th>Symbol</th>
                  <th>Signal</th>
                  <th>Confidence</th>
                  <th>Prob Up</th>
                  <th>Model</th>
                </tr>
              </thead>
              <tbody>
                {(scanner?.rows ?? []).map((row) => (
                  <tr key={`${row.symbol}-${row.timeframe}`}>
                    <td>{row.symbol}</td>
                    <td>{row.approved_signal}</td>
                    <td>{formatPercent(row.confidence)}</td>
                    <td>{formatPercent(row.prob_up)}</td>
                    <td>{row.model_name}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </article>
      </section>

      <footer className="footer">
        <span>Prediction time: {latestSignal ? formatTs(latestSignal.prediction_ts) : "N/A"}</span>
        <span>Target time: {latestSignal ? formatTs(latestSignal.target_ts) : "N/A"}</span>
      </footer>
    </div>
  );
}
