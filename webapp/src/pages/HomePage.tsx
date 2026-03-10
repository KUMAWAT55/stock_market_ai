import { Link } from "react-router-dom";

export default function HomePage() {
  return (
    <main className="page-shell">
      <section className="marketing-hero">
        <p className="kicker">Realtime Intraday Intelligence</p>
        <h1>TradeIQ</h1>
        <p>
          Intraday-first analytics platform with live data, multi-timeframe model predictions, strategy backtesting,
          and scanner workflows.
        </p>
        <div className="hero-actions">
          <Link to="/dashboard" className="btn-primary">Open Dashboard</Link>
          <Link to="/about" className="btn-ghost">Learn More</Link>
        </div>
      </section>

      <section className="feature-grid">
        <article className="feature-card">
          <h3>Live Data + Charting</h3>
          <p>Streaming candles with overlays and model context for fast intraday decisions.</p>
        </article>
        <article className="feature-card">
          <h3>Model Matrix</h3>
          <p>Compare predictions across 1m/5m/15m/1h/1d timeframes in one view.</p>
        </article>
        <article className="feature-card">
          <h3>Strategy Lab</h3>
          <p>Streak-style quick backtests for indicator conditions before deploying ideas.</p>
        </article>
        <article className="feature-card">
          <h3>Scanner</h3>
          <p>Rank opportunities by confidence and approved risk-aware signal.</p>
        </article>
      </section>
    </main>
  );
}
