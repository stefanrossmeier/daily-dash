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

Do not use topic quotas. Apply the broad-market objective through `rank_score`.
DailyDash will preserve the LLM's ordering judgment rather than applying a
hand-written company-vs-macro filter.

## Material transmission discipline

`market_breadth` measures how widely an event could transmit. It does NOT by
itself measure how important the event is. A story must not receive a high
`rank_score` merely because its possible consequences span countries, sectors
or asset classes.

For Top News, the strongest candidates combine BOTH:

1. broad transmission; and
2. a concrete, material and reasonably immediate mechanism for repricing.

Examples of concrete transmission mechanisms include:

- a changed expected path for central-bank policy or market interest rates;
- a material inflation, employment, growth or liquidity surprise;
- a fiscal, tax, trade, sanctions or regulatory action large enough to change
  economic or market expectations;
- a disruption to energy, commodities, supply chains or credit conditions;
- a geopolitical escalation that materially changes those economic channels;
- an exceptionally large mega-cap event that can directly move a broad index
  or credibly reprice an economy-wide investment theme.

Broad but weak, symbolic, procedural or speculative developments should rank
low when the candidate does not establish a concrete market mechanism. Do not
promote diplomatic symbolism, political rhetoric or hypothetical escalation
merely because many markets could theoretically react to a future development.

As an internal consistency check for this profile:

- `rank_score >= 75` should normally require both `market_breadth >= 60` and
  `market_impact >= 50`;
- `rank_score >= 60` should normally require both `market_breadth >= 50` and
  `market_impact >= 40`.

These are guidance, not a mathematical formula. Exceptionally strong evidence
may justify an exception, but the rationale must name the concrete broad-market
transmission mechanism.

A candidate with high `market_breadth` but weak `market_impact` should normally
rank below a candidate with somewhat narrower breadth but substantially stronger,
more immediate market impact.

## New information versus commentary

Prefer actual new catalysts over previews, reactions, strategist commentary or
opinion about a catalyst that has not changed.

An article that merely says investors are waiting for a speech, speculates about
what a policymaker may say, or comments on the likely interpretation of an
already-known event should normally rank below the actual policy decision,
speech, data release or new factual development.

When multiple candidates are primarily previews, reactions or commentary about
the same upcoming or already-known catalyst, treat them as duplicate coverage
unless one contains materially new independent information. They should not
consume multiple Top News positions simply because different publishers frame
the same catalyst differently.

## Single-company exception remains narrow

Do not suppress a company story merely because it concerns one issuer. A
mega-cap event can legitimately rank near the top when the candidate evidence
supports exceptional and immediate broad-index impact or an economy-wide
transmission mechanism. The distinction is not "macro versus company"; the
distinction is "broad material repricing versus isolated repricing".

