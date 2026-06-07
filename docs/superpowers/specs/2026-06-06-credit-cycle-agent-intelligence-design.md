# Credit Cycle Agent Intelligence Design

## Context

This design defines a roadmap from public economic content to an agent-ready information layer for credit cycle intelligence.

The inspiration is Ray Dalio's explanation of the economic machine: credit cycles, debt, interest rates, liquidity, deleveraging, and recoveries drive much of the macro environment. The product bet is that these concepts can become a structured, recurring intelligence layer that is useful first to people and later to AI agents.

The product should not copy existing financial agent reference systems. The focus is different: not agents producing financial work products for analysts, but a structured economic context layer that humans can read and agents can consume.

## Product Shape

The product is **Credit Cycle Intelligence**: a content-first product with an agent-ready data foundation.

First public product:

- Telegram-first short posts for observations, charts, explanations, and audience feedback.
- A weekly **Global Credit Cycle Brief** covering five regions: United States, Eurozone, China, Japan, and United Kingdom.
- A practical portfolio context tone, including risk signals, but no personalized investment recommendations.

Internal source of truth:

- Each weekly brief is generated from a structured snapshot.
- The snapshot stores credit cycle phase, key signals, macro backdrop, market stress, portfolio risk context, confidence, sources, and weekly narratives.
- Snapshots start as JSON/YAML/Markdown registry artifacts and can later become API or MCP outputs.

Core promise:

> Help private investors and macro/finance enthusiasts understand which phase of the credit cycle key regions are in, and how that changes portfolio risk.

## Audience And Job To Be Done

Primary audience:

- Private investors who want to understand market risk without reading institutional macro research.
- Macro/finance enthusiasts who like depth, charts, and explanations and can become an early community.

Main job to be done:

- Understand the current credit cycle phase across key regions.
- Understand how changes in credit conditions affect portfolio risk.

The product should provide decision support and risk context, not personal financial advice.

## MVP Scope

The MVP is intentionally narrow.

Included:

- Regions: `US`, `Eurozone`, `China`, `Japan`, `UK`.
- Frequency: weekly snapshot and weekly brief.
- Data format: JSON snapshot as the primary machine-readable artifact.
- Public format: Markdown weekly brief and Telegram post drafts.
- Automation: a pipeline that collects a limited set of reliable indicators and reproducibly generates snapshots.
- Agent-ready layer: structured local files first, not MCP/API in the MVP.

Excluded from MVP:

- Full dashboard.
- Public API.
- MCP server.
- Personalized portfolio recommendations.
- Buy/sell recommendations.
- Machine learning classification.

Expected artifacts:

```text
data/snapshots/YYYY-MM-DD/global-credit-cycle.json
data/registry/regions.yaml
content/briefs/YYYY-MM-DD-global-credit-cycle-brief.md
content/telegram/YYYY-MM-DD-posts.md
```

## Source Strategy

The source universe is prioritized by reliability and reproducibility.

### Tier 1: Core Official Sources

Tier 1 sources should be used as the foundation for credit cycle classification.

- BIS Data Portal (`https://data.bis.org/`): cross-country credit metrics, including credit to non-financial sectors, household credit, corporate credit, and government credit. BIS provides bulk downloads and data portal access.
- FRED / St. Louis Fed (`https://fred.stlouisfed.org/docs/api/fred/series_observations.html`): US rates, yield curve, credit spreads, labor data, inflation data, and financial stress proxies.
- ECB Data Portal (`https://data.ecb.europa.eu/help/api/data`): Eurozone rates, monetary and financial data, yield data, and related macro-financial series.
- ECB Bank Lending Survey (`https://www.ecb.europa.eu/stats/ecb_surveys/bank_lending_survey/html/index.en.html`): Eurozone lending standards and credit demand/supply conditions.
- Bank of Japan statistics/API (`https://www.boj.or.jp/en/statistics/outline/notice_2026/not260218a.htm`): Japan time-series data for rates, monetary indicators, and credit-related indicators.
- People's Bank of China (`https://www.pbc.gov.cn/en/3688247/3688975/4505202/4505205/index.html`): aggregate financing to the real economy, loans, money supply, and monetary reports.
- National Bureau of Statistics of China (`https://www.stats.gov.cn/english/`): macro backdrop for China, including growth, prices, and activity data.

### Tier 2: Official Or Institutional Complements

Tier 2 sources can support normalization, fallback data, and broader context.

- World Bank Data (`https://datacatalog.worldbank.org/`): cross-country debt and credit context.
- OECD Data and reports (`https://www.oecd.org/en/data.html`): developed-market macro-financial and debt context.
- IMF Data: cross-country financial, fiscal, external, and debt context.
- Bank of England Database: UK rates, monetary statistics, lending, credit, and macro-financial data.

### Tier 3: Market Proxies

Tier 3 sources are useful for market stress context but should not be the sole basis for phase classification.

- Credit spreads.
- Sovereign yield curves.
- Bank equity or financial stress proxies.
- Volatility proxies.
- Currency pressure.
- Gold, crypto, and high-beta risk asset context.

### Source Rule

The credit cycle phase must be grounded in Tier 1 or Tier 2 data. News, narratives, and market proxies can explain the phase or adjust confidence, but they cannot be the only basis for classification.

Each indicator should have a source registry entry:

```yaml
indicator: private_nonfinancial_credit_to_gdp
regions: [US, Eurozone, China, Japan, UK]
primary_source: BIS
frequency: quarterly
access_method: bulk_csv_or_sdmx
used_for:
  - credit_cycle_state
  - leverage_context
fallback_source: World Bank
confidence_weight: high
```

## Data Model

The snapshot must be understandable by both humans and agents.

Top-level structure:

```json
{
  "as_of": "2026-06-06",
  "version": "0.1",
  "global_summary": {
    "risk_regime": "neutral_to_defensive",
    "headline": "Credit conditions remain tight across developed markets.",
    "confidence": "medium"
  },
  "regions": []
}
```

Each region contains six layers.

### Credit Cycle State

```json
{
  "credit_cycle": {
    "phase": "tightening",
    "confidence": "medium",
    "weekly_change": "unchanged",
    "rationale": [
      "Policy remains restrictive",
      "Credit spreads are stable",
      "Bank lending standards remain tight"
    ]
  }
}
```

Allowed phases:

- `easing`
- `expansion`
- `tightening`
- `stress`
- `deleveraging`
- `recovery`

### Macro Backdrop

```json
{
  "macro_backdrop": {
    "inflation_trend": "cooling",
    "growth_trend": "slowing",
    "labor_market_trend": "softening",
    "central_bank_stance": "restrictive",
    "liquidity_impulse": "negative"
  }
}
```

### Market Stress

```json
{
  "market_stress": {
    "yield_curve": "inverted",
    "credit_spreads": "stable",
    "financial_stress": "contained",
    "volatility": "low",
    "currency_pressure": "low"
  }
}
```

### Portfolio Risk Context

```json
{
  "portfolio_risk_context": {
    "equities": "late-cycle caution",
    "duration_bonds": "watch for easing transition",
    "cash": "still attractive",
    "gold": "neutral_to_positive",
    "crypto_high_beta": "sensitive_to_liquidity"
  }
}
```

### Narratives And Weekly Changes

Narratives explain what changed and why it matters. They are not random news items; they must affect credit conditions, liquidity, portfolio risk, or confidence.

```json
{
  "narratives": [
    {
      "title": "Bank lending standards remain tight",
      "type": "credit_conditions",
      "region": "US",
      "importance": "high",
      "summary": "Loan officer data still points to restrictive lending conditions.",
      "impact": "Supports tightening or stress interpretation.",
      "sources": []
    }
  ],
  "weekly_changes": [
    {
      "region": "Eurozone",
      "change": "credit_spreads_widened",
      "importance": "medium",
      "interpretation": "Market stress increased but remains below crisis levels."
    }
  ]
}
```

### Sources And Data Gaps

Each region must include sources for the major signals and data gaps when inputs are stale or missing.

```json
{
  "sources": [
    {
      "name": "BIS",
      "url": "https://data.bis.org/",
      "indicator": "private_nonfinancial_credit_to_gdp",
      "observed_at": "2026-03-31",
      "fetched_at": "2026-06-06"
    }
  ],
  "data_gaps": [
    {
      "indicator": "bank_lending_standards",
      "severity": "medium",
      "effect": "phase_confidence_reduced"
    }
  ]
}
```

## Pipeline Architecture

The MVP pipeline has seven stages.

### 1. Source Fetch

Collect a limited set of reliable indicators for five regions from the source registry.

The first implementation should prefer official APIs or bulk downloads over web scraping.

### 2. Normalize

Normalize data into a common internal shape:

- region
- indicator
- value
- date
- frequency
- source
- last_updated

### 3. Signal Evaluation

Translate raw metrics into qualitative signal states:

- `rising`, `falling`, `stable`
- `tight`, `loose`, `neutral`
- `stress_low`, `stress_medium`, `stress_high`

### 4. Phase Classification

Classify the credit cycle phase using transparent rule-based logic.

No ML is used in the MVP. Rules are easier to explain, audit, and adjust.

### 5. Snapshot Generation

Generate weekly JSON/YAML snapshots containing:

- global summary
- five regional blocks
- confidence
- rationale
- sources
- narratives and weekly changes
- data gaps

### 6. Brief Generation

Generate Markdown drafts for:

- weekly global credit cycle brief
- Telegram post ideas

Human review remains required before publication.

### 7. Validation

Validate that:

- all five regions are present
- required fields exist
- critical data is not stale without a data gap note
- each phase has rationale
- major conclusions have sources
- confidence is reduced when required data is missing

## Classification Model

The MVP uses rule-based classification.

Each region receives intermediate assessments:

- `credit_conditions`: easing / neutral / tight / stressed
- `leverage_context`: low / moderate / high / extreme
- `macro_backdrop`: supportive / mixed / deteriorating
- `market_stress`: low / medium / high
- `policy_stance`: easing / neutral / restrictive

These produce `credit_cycle.phase`.

The classifier must always produce:

- phase
- confidence
- rationale
- data gaps, when relevant

If data is insufficient, the system should avoid overconfidence. It should reduce confidence and explain the missing inputs.

## Publishing Workflow

Weekly flow:

1. Pipeline updates source data.
2. Pipeline generates the weekly JSON snapshot.
3. Validation checks completeness, freshness, sources, and confidence.
4. Pipeline generates a Markdown weekly brief draft.
5. Human editor reviews tone, narratives, caution, and portfolio risk context.
6. Telegram post drafts are created from the weekly brief.
7. Snapshot, brief, and posts are saved as versioned artifacts.

The pipeline automates collection, structure, and first-pass classification. A human remains responsible for final interpretation and publication.

## Success Criteria For 2-4 Weeks

The MVP is successful if:

- 2-4 weekly snapshots are created without manual JSON editing.
- Each snapshot covers all five regions.
- Each region has phase, confidence, rationale, sources, data gaps when needed, and portfolio risk context.
- 2-4 public weekly briefs are published.
- 10-20 Telegram posts are produced from weekly material.
- Early demand signals are collected:
  - subscribers
  - replies
  - reposts
  - saves
  - questions from readers
  - requests for a dashboard, API, or MCP access

## Risks And Mitigations

### Risk: Building Infrastructure Before Demand

Mitigation: keep the public weekly brief as the primary validation surface. The structured snapshot is required, but dashboard/API/MCP are excluded from MVP.

### Risk: Overclaiming Investment Signals

Mitigation: frame output as portfolio risk context and decision support, not personalized advice or buy/sell recommendations.

### Risk: Weak Or Inconsistent Data Across Regions

Mitigation: use a source registry, show data gaps, reduce confidence when inputs are stale or missing, and avoid pretending precision.

### Risk: The Model Becomes Too Broad

Mitigation: credit cycle state remains the core. Macro backdrop, market stress, narratives, and portfolio context explain the cycle; they do not replace it.

### Risk: Agent-Ready Format Is Too Vague

Mitigation: every weekly brief must be generated from a structured snapshot. This creates machine-readable discipline before API/MCP work begins.

## Future Extensions

After validation:

- Public dashboard with regional credit cycle map.
- API endpoints for region and global credit cycle state.
- MCP server for agent queries.
- Historical snapshot archive and phase-change detection.
- Paid weekly brief.
- Premium agent-ready data subscription.
