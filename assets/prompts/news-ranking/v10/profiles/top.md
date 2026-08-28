# Profile: Top News

Top News is a broad-market briefing, not a list of the most dramatic financial
headlines and not a list of the stocks with the largest individual moves.

The primary question is:

> Could this development materially change the direction, level, volatility or
> expectations of a broad equity index such as the S&P 500 or Nasdaq, major
> interest-rate markets, FX, commodities, credit, or global risk positioning?

## Ranking objective

Prefer, in this order:

1. macroeconomic, monetary-policy, fiscal, geopolitical, energy, liquidity or
   systemic developments with broad or cross-asset consequences;
2. developments likely to move a broad equity index or materially change
   economy-wide expectations;
3. major sector or thematic developments with credible spillover into broad
   indexes or several asset classes;
4. single-company developments only when they contain credible broad-market
   transmission;
5. ordinary company-specific earnings, guidance, product, analyst or price-move
   stories.

## Single-company discipline

Do not give a high `rank_score` to a story merely because:

- the company is famous or has a large market capitalization;
- its own stock moved sharply;
- it reported an earnings beat or miss;
- it is a member of a major index;
- the article describes substantial implications for that company alone.

An individual-company event may still rank highly when the candidate evidence
supports a plausible broad-market transmission mechanism, for example because
the company has enough index weight to move a broad benchmark materially, the
news changes expectations for a major economy-wide investment cycle, or it is a
credible signal about demand, inflation, credit, supply chains or another broad
market driver. Do not infer such transmission automatically.

For an event whose consequences are primarily confined to one company,
`market_breadth` should normally be below 50 and `rank_score` should normally
remain below genuinely broad-market developments.

A spectacular move in one stock is less important for this profile than a
smaller-looking development that changes the expected path of rates, inflation,
growth, liquidity, energy prices, trade policy, credit conditions or broad risk
sentiment.

## Composition of the final report

If enough genuinely broad-market developments exist in the candidate set, they
should dominate the selected Top News items. Single-company stories may fill
remaining positions, but they should not crowd broad-market catalysts out of the
top of the ranking.

Do not use topic quotas, do not try to fill a fixed item count, and do not infer
importance from publisher identity.
Return internally consistent semantic values for every headline. DailyDash will
combine those model-provided values with a transparent deterministic policy so
that narrow breadth and weak market impact cannot be hidden by an inflated
`rank_score`.

## Recall and breadth discipline

Top News should rank macroeconomic, systemic and broad cross-asset developments
first, but it is not a macro-only feed. Significant sector, corporate,
technology, regulatory or geopolitical developments may still deserve
selection when they are materially useful to a market-focused reader.

Do not reduce `market_impact`, `market_breadth` or `rank_score` merely because a
story is not a classic macro headline. Score the actual transmission supported
by the headline. A narrower story should usually rank below stronger macro news,
not automatically disappear.

Treat aggregate information about the corporate sector, households, labor,
demand, profits, financing conditions or broad production as potentially broad
market information when the headline clearly describes an economy-wide or
market-wide condition rather than one isolated company.

When the evidence supports a plausible material market consequence but the
exact magnitude is uncertain, avoid artificially low scores solely to enforce a
short final list. DailyDash applies a separate transparent deterministic policy
to the semantic scores.
