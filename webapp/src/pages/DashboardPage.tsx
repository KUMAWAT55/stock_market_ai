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
  return `${dt.toLocaleString("en-IN", { hour12: false, timeZone: "Asia/Kolkata" })} IST`;
}

function formatPredictionWindow(timeframe?: string | null, targetTs?: string | null): string {
  if (!timeframe && !targetTs) return "N/A";
  const targetLabel = formatTs(targetTs);
  if (!timeframe) return targetLabel;
  if (targetLabel === "N/A") return timeframe;
  return `${timeframe} → ${targetLabel}`;
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

function signalClass(value?: string | null): string {
  const normalized = String(value ?? "").toUpperCase();
  if (normalized === "BEARISH") return "signal signal-bearish";
  if (normalized === "BULLISH") return "signal signal-bullish";
  if (normalized === "HOLD" || normalized === "NEUTRAL") return "signal signal-neutral";
  return "signal";
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
    () => {
      const isIntraday = timeframe !== "1d";
      const rangebreaks = [
        { bounds: ["sat", "mon"] },
        ...(isIntraday ? [{ bounds: [15.5, 9.25], pattern: "hour" as const }] : []),
      ];
      return {
      margin: { l: 30, r: 20, t: 10, b: 30 },
      plot_bgcolor: "#0f1219",
      paper_bgcolor: "#0f1219",
      xaxis: {
        type: "date",
        rangeslider: { visible: false },
        color: "#b4bac8",
        rangebreaks,
        tickformat: "%H:%M\n%b %d",
        hoverformat: "%Y-%m-%d %H:%M",
      },
      yaxis: { color: "#b4bac8", fixedrange: false },
      legend: { orientation: "h", y: 1.12, x: 0 },
      // Keep user zoom/pan when candles refresh for same symbol+timeframe.
      uirevision: `${symbol}:${timeframe}`,
      };
    },
    [symbol, timeframe],
  );

  const latestSignal = snapshot?.signal_history?.rows?.[0] ?? null;
  const latestSignalValue = latestSignal?.risk_snapshot?.approved_signal ?? latestSignal?.signal ?? "N/A";
  const lastPrice = snapshot?.live_price?.last_price ?? null;
  const ruleProfile = snapshot?.rules?.rules ?? {};
  const lagHeatmap = snapshot?.indicator_heatmap_lag ?? snapshot?.indicator_heatmap;
  const leadHeatmap = snapshot?.indicator_heatmap_lead ?? snapshot?.indicator_heatmap;

  const renderHeatmap = (
    title: string,
    payload: SnapshotPayload["indicator_heatmap"] | undefined,
    tooltip: string,
  ) => {
    if (!payload) {
      return (
        <section className="panel tooltip-target" data-tooltip={tooltip}>
          <div className="panel-head">
            <h3>{title}</h3>
            <span>No data</span>
          </div>
          <div className="empty-state">No indicator data available.</div>
        </section>
      );
    }

    return (
      <section className="panel tooltip-target" data-tooltip={tooltip}>
        <div className="panel-head">
          <h3>{title}</h3>
          <span>Bullish/Bearish map for each timeframe</span>
        </div>
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Indicator</th>
                {payload.timeframes.map((tf) => (
                  <th key={tf}>{tf}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {payload.heatmap_rows.map((row) => (
                <tr key={row.indicator}>
                  <td>{row.label}</td>
                  {payload.timeframes.map((tf) => (
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
    );
  };

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

      <section
        className="controls tooltip-target"
        data-tooltip="Core filters that drive all panels: symbol, timeframe, refresh cadence, and row limits."
      >
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
        <article
          className="metric-card tooltip-target"
          data-tooltip="Latest price snapshot from the live engine or recent candle. Useful for verifying feed health."
        >
          <p>Live Price</p>
          <h2>{lastPrice ? `₹ ${lastPrice.toFixed(2)}` : "N/A"}</h2>
          <small>{snapshot?.live_price?.source ?? "No source"}</small>
        </article>
        <article
          className="metric-card tooltip-target"
          data-tooltip="Most recent model output for this symbol/timeframe after risk gating. Helps track the latest stance."
        >
          <p>Primary Signal</p>
          <h2 className={signalClass(latestSignalValue)}>{latestSignalValue}</h2>
          <small>{latestSignal ? `Confidence ${formatPercent(latestSignal.confidence)}` : "No prediction yet"}</small>
          <small>
            {latestSignal
              ? `Period ${snapshot?.timeframe ?? "N/A"} · Target ${formatTs(latestSignal.target_ts)}`
              : "Period N/A"}
          </small>
        </article>
        <article
          className="metric-card tooltip-target"
          data-tooltip="Aggregated consensus across timeframes. Useful for checking multi-timeframe alignment."
        >
          <p>Matrix Consensus</p>
          <h2 className={signalClass(snapshot?.model_matrix?.consensus?.signal ?? "N/A")}>
            {snapshot?.model_matrix?.consensus?.signal ?? "N/A"}
          </h2>
          <small>{formatPercent(snapshot?.model_matrix?.consensus?.avg_confidence)}</small>
        </article>
        <article
          className="metric-card tooltip-target"
          data-tooltip="Live engine status and tick health. Dropped ticks indicate feed pressure or backpressure."
        >
          <p>Engine Stream</p>
          <h2>{snapshot?.engine?.details?.ws_connected ? "Connected" : "Disconnected"}</h2>
          <small>Dropped ticks: {snapshot?.engine?.details?.dropped_ticks ?? 0}</small>
        </article>
      </section>

      <section className="layout-main">
        <article
          className="panel tooltip-target"
          data-tooltip="Recent OHLC candles with EMA overlays. Use this to visually validate trend and price action."
        >
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

        <article
          className="panel tooltip-target"
          data-tooltip="Risk and threshold settings for this timeframe plus a runtime backtest summary."
        >
          <div className="panel-head">
            <h3>Timeframe Rules</h3>
          </div>
          <div className="kv-list">
            <div><span>Bullish Threshold</span><b>{formatPercent(ruleProfile.signal_bullish_threshold)}</b></div>
            <div><span>Bearish Threshold</span><b>{formatPercent(ruleProfile.signal_bearish_threshold)}</b></div>
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

      <section
        className="panel tooltip-target"
        data-tooltip="Latest model outputs across all timeframes for this symbol. Helps compare alignment and confidence."
      >
        <div className="panel-head">
          <h3>Model Matrix Across Timeframes</h3>
          <span>
            Consensus:{" "}
            <span className={signalClass(snapshot?.model_matrix?.consensus?.signal ?? "N/A")}>
              {snapshot?.model_matrix?.consensus?.signal ?? "N/A"}
            </span>
          </span>
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
                <th>Target</th>
                <th>Model</th>
                <th>Version</th>
                <th>Risk Note</th>
              </tr>
            </thead>
            <tbody>
              {(snapshot?.model_matrix?.rows ?? []).map((row) => (
                <tr key={row.timeframe}>
                  <td>{row.timeframe}</td>
                  <td>
                    <span className={signalClass(row.signal)}>{row.signal ?? "N/A"}</span>
                  </td>
                  <td>
                    <span className={signalClass(row.approved_signal)}>{row.approved_signal ?? "N/A"}</span>
                  </td>
                  <td>{formatPercent(row.confidence)}</td>
                  <td>{formatPercent(row.prob_up)}</td>
                  <td>{formatTs(row.target_ts)}</td>
                  <td>{row.model_name ?? "N/A"}</td>
                  <td>{row.model_version ?? "N/A"}</td>
                  <td>{row.risk_reason ?? "-"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      {renderHeatmap(
        "Lag Indicator Heatmap",
        lagHeatmap,
        "Lagging indicator bias by timeframe. Useful for confirming trend-following alignment.",
      )}
      {renderHeatmap(
        "Lead Indicator Heatmap",
        leadHeatmap,
        "Leading indicator bias by timeframe. Useful for spotting early momentum shifts.",
      )}

      <section className="layout-split">
        <article
          className="panel tooltip-target"
          data-tooltip="Quick strategy backtest on recent candles. Useful for testing indicator logic before deployment."
        >
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
            <div>
              <span>Latest Signal</span>
              <b className={signalClass(strategyBacktest?.latest_signal ?? "N/A")}>
                {strategyBacktest?.latest_signal ?? "N/A"}
              </b>
            </div>
            <div><span>Trades</span><b>{strategyBacktest?.trade_count ?? 0}</b></div>
            <div><span>Win Rate</span><b>{formatPercent(strategyBacktest?.win_rate)}</b></div>
            <div><span>Total Return</span><b>{formatPercent(strategyBacktest?.total_return)}</b></div>
            <div><span>Max DD</span><b>{formatPercent(strategyBacktest?.max_drawdown)}</b></div>
            <div><span>Sharpe-like</span><b>{(strategyBacktest?.sharpe_like ?? 0).toFixed(2)}</b></div>
            <div><span>Period</span><b>{timeframe}</b></div>
          </div>
          <p className="note">{strategyBacktest?.strategy_note ?? ""}</p>
        </article>

        <article
          className="panel tooltip-target"
          data-tooltip="Ranked intraday opportunities by signal confidence. Use to spot high-conviction candidates."
        >
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
                {["ALL", "BULLISH", "BEARISH", "HOLD"].map((item) => (
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
                  <th>TF</th>
                  <th>Signal</th>
                  <th>Confidence</th>
                  <th>Prob Up</th>
                  <th>Target</th>
                  <th>Model</th>
                </tr>
              </thead>
              <tbody>
                {(scanner?.rows ?? []).map((row) => (
                  <tr key={`${row.symbol}-${row.timeframe}`}>
                    <td>{row.symbol}</td>
                    <td>{row.timeframe}</td>
                    <td>
                      <span className={signalClass(row.approved_signal)}>{row.approved_signal}</span>
                    </td>
                    <td>{formatPercent(row.confidence)}</td>
                    <td>{formatPercent(row.prob_up)}</td>
                    <td>{formatTs(row.target_ts)}</td>
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
        <span>Prediction period: {formatPredictionWindow(snapshot?.timeframe ?? null, latestSignal?.target_ts)}</span>
      </footer>
    </div>
  );
}
