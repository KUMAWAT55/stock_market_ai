export default function AboutPage() {
  return (
    <main className="page-shell about-page">
      <section className="about-hero">
        <div className="about-hero-copy">
          <p className="kicker">About TradeIQ</p>
          <h1>Research-grade signals, delivered like a trading console.</h1>
          <p className="subtitle">
            TradeIQ is built for intraday desks that want live model output, rich context, and compliance-ready
            research workflows. Every screen is tuned for speed, interpretability, and an operator mindset.
          </p>
          <div className="about-pill-row">
            <span className="about-pill">Realtime model matrix</span>
            <span className="about-pill">Indicator heatmaps</span>
            <span className="about-pill">Strategy backtests</span>
            <span className="about-pill">Risk governance</span>
          </div>
        </div>
        <div className="about-hero-visual">
          <div className="hero-signal-card">
            <div className="hero-signal-header">
              <span>Signal Pulse</span>
              <strong>14:32 IST</strong>
            </div>
            <div className="hero-signal-grid">
              <div>
                <p>Momentum</p>
                <h3 className="signal signal-bullish">Bullish</h3>
                <span className="pulse-dot" />
              </div>
              <div>
                <p>Confidence</p>
                <h3>0.78</h3>
              </div>
              <div>
                <p>Risk</p>
                <h3>Managed</h3>
              </div>
              <div>
                <p>Horizon</p>
                <h3>15m</h3>
              </div>
            </div>
          </div>
          <div className="about-stat-grid">
            <div>
              <p>Models tracked</p>
              <h3>9</h3>
            </div>
            <div>
              <p>Signals per session</p>
              <h3>3,200+</h3>
            </div>
            <div>
              <p>Research workflows</p>
              <h3>5</h3>
            </div>
            <div>
              <p>Latency target</p>
              <h3>&lt;120ms</h3>
            </div>
          </div>
        </div>
      </section>

      <section className="about-section">
        <div className="section-header">
          <h2>UI Snapshots</h2>
          <p>Representative views of the dashboard UI, styled to mirror the live product.</p>
        </div>
        <div className="ui-gallery">
          <article className="ui-card">
            <div className="ui-image">
              <svg viewBox="0 0 520 300" role="img" aria-label="Signal matrix panel mockup">
                <defs>
                  <linearGradient id="matrixGlow" x1="0" y1="0" x2="1" y2="1">
                    <stop offset="0" stopColor="#1ea1ff" stopOpacity="0.5" />
                    <stop offset="1" stopColor="#0e2b4f" stopOpacity="0.2" />
                  </linearGradient>
                </defs>
                <rect x="8" y="8" width="504" height="284" rx="18" fill="#0f1826" stroke="#273851" />
                <rect x="28" y="28" width="180" height="18" rx="6" fill="#1e2b3f" />
                <rect x="28" y="58" width="460" height="60" rx="10" fill="url(#matrixGlow)" />
                <g fill="#1d2a3e">
                  <rect x="28" y="132" width="140" height="40" rx="8" />
                  <rect x="178" y="132" width="140" height="40" rx="8" />
                  <rect x="328" y="132" width="160" height="40" rx="8" />
                  <rect x="28" y="182" width="200" height="40" rx="8" />
                  <rect x="238" y="182" width="250" height="40" rx="8" />
                </g>
                <circle cx="68" cy="78" r="10" fill="#2dc781" />
                <circle cx="108" cy="78" r="10" fill="#ffb44c" />
                <circle cx="148" cy="78" r="10" fill="#ef5f5f" />
              </svg>
            </div>
            <h3>Signal Matrix</h3>
            <p>Cross-timeframe consensus with risk overlays to keep entry decisions crisp.</p>
          </article>

          <article className="ui-card">
            <div className="ui-image">
              <svg viewBox="0 0 520 300" role="img" aria-label="Heatmap panel mockup">
                <defs>
                  <linearGradient id="heatGlow" x1="0" y1="0" x2="1" y2="1">
                    <stop offset="0" stopColor="#4cfcff" stopOpacity="0.4" />
                    <stop offset="1" stopColor="#093e83" stopOpacity="0.2" />
                  </linearGradient>
                </defs>
                <rect x="8" y="8" width="504" height="284" rx="18" fill="#0f1826" stroke="#273851" />
                <rect x="26" y="26" width="220" height="18" rx="6" fill="#1e2b3f" />
                <rect x="26" y="58" width="468" height="200" rx="12" fill="url(#heatGlow)" />
                <g>
                  {Array.from({ length: 5 }).map((_, row) =>
                    Array.from({ length: 7 }).map((__, col) => (
                      <rect
                        key={`${row}-${col}`}
                        x={40 + col * 64}
                        y={76 + row * 34}
                        width="52"
                        height="22"
                        rx="6"
                        fill={row % 2 === 0 ? "#1c2a3f" : "#223149"}
                      />
                    )),
                  )}
                </g>
                <rect x="26" y="270" width="320" height="10" rx="5" fill="#1e2b3f" />
              </svg>
            </div>
            <h3>Indicator Heatmap</h3>
            <p>Lagging and leading indicators mapped to a glanceable grid for fast bias checks.</p>
          </article>

          <article className="ui-card">
            <div className="ui-image">
              <svg viewBox="0 0 520 300" role="img" aria-label="Backtest panel mockup">
                <defs>
                  <linearGradient id="chartGlow" x1="0" y1="0" x2="1" y2="1">
                    <stop offset="0" stopColor="#02385f" stopOpacity="0.35" />
                    <stop offset="1" stopColor="#000000" stopOpacity="0.2" />
                  </linearGradient>
                </defs>
                <rect x="8" y="8" width="504" height="284" rx="18" fill="#0f1826" stroke="#273851" />
                <rect x="26" y="26" width="210" height="18" rx="6" fill="#1e2b3f" />
                <rect x="26" y="58" width="468" height="140" rx="12" fill="url(#chartGlow)" />
                <polyline
                  points="40,174 86,142 132,154 178,120 224,136 270,104 316,112 362,88 408,102 454,70"
                  fill="none"
                  stroke="#0d3eee"
                  strokeWidth="3"
                />
                <g fill="#1d2a3e">
                  <rect x="26" y="214" width="140" height="40" rx="8" />
                  <rect x="178" y="214" width="140" height="40" rx="8" />
                  <rect x="330" y="214" width="164" height="40" rx="8" />
                </g>
              </svg>
            </div>
            <h3>Strategy Backtests</h3>
            <p>Turn model events into realized returns with fast, parameterized experiments.</p>
          </article>
        </div>
      </section>

      <section className="about-section">
        <div className="section-header">
          <h2>Operating System for Intraday Research</h2>
          <p>From ingestion to audit trails, the flow is built for decision quality and speed.</p>
        </div>
        <div className="flow-grid">
          <article className="flow-card">
            <span className="flow-badge">01</span>
            <h3>Market Intake</h3>
            <p>Live ticks and candles flow through reliability checks before hitting the model stack.</p>
          </article>
          <article className="flow-card">
            <span className="flow-badge">02</span>
            <h3>Model Inference</h3>
            <p>Timeframe-specific models output probability vectors and confidence-ranked signals.</p>
          </article>
          <article className="flow-card">
            <span className="flow-badge">03</span>
            <h3>Context Layer</h3>
            <p>Heatmaps, scanner outputs, and rule profiles explain why a signal is approved.</p>
          </article>
          <article className="flow-card">
            <span className="flow-badge">04</span>
            <h3>Research Outputs</h3>
            <p>Backtests, watchlists, and risk overlays are packed for compliance-safe review.</p>
          </article>
        </div>
      </section>

      <section className="content-card">
        <h2>Core Principles</h2>
        <ul className="plain-list">
          <li>Intraday-first UX and analytics.</li>
          <li>Clear model explainability with governance baked in.</li>
          <li>Research-only architecture with compliance-safe design.</li>
        </ul>
      </section>

      <section className="content-card">
        <h2>Owner</h2>
        <ul className="plain-list">
          <li>Rohit Kumawat - rhtkumawat55@gmail.com</li>
        </ul>
      </section>
    </main>
  );
}
