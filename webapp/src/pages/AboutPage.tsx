export default function AboutPage() {
  return (
    <main className="page-shell">
      <section className="content-card">
        <h1>About TradeIQ</h1>
        <p>
          TradeIQ is built for serious intraday traders who need fast, interpretable model outputs along with
          technical context and strategy research tools.
        </p>
        <p>
          The platform combines live market ingestion, feature engineering, model inference, and risk governance into
          one workflow. The dashboard surfaces model matrix, indicator heatmap, scanner, and strategy backtests.
        </p>
      </section>
      <section className="content-card">
        <h2>Core Principles</h2>
        <ul className="plain-list">
          <li>Intraday-first UX and analytics.</li>
          <li>Clear model explainability and risk context.</li>
          <li>Research-only architecture with compliance-safe design.</li>
        </ul>
      </section>
    </main>
  );
}
