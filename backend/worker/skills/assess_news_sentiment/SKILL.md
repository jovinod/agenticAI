---
name: assess_news_sentiment
description: Use when recent news about a company might be relevant to whether it's currently a sound investment — helps distinguish routine negative coverage from genuine red flags.
---

# Assessing News Sentiment

Not all negative news is equally important. Your job is to judge whether recent news
coverage represents a **genuine cause for investor concern** — not to count positive
versus negative words, and not to flag anything that merely sounds bad.

## Genuine red flags (weigh these heavily)

- Allegations of fraud, accounting irregularities, or regulatory violations
- A CEO, CFO, or other key executive departing suddenly or "under a cloud"
  (unexplained resignation, board conflict, forced-out framing)
- A formal regulatory investigation or lawsuit with material financial exposure
- A major product recall, safety failure, or data breach
- A significant, unexpected revenue/guidance miss reported as a genuine surprise
  to the market — not something already anticipated

## Routine coverage — do NOT flag these, even if the tone reads negatively

- General market commentary or analyst opinion pieces ("Is $TICKER overvalued?")
- Ordinary competitive pressure or a mixed product review
- Short-term stock price movement described neutrally ("shares dipped after...")
- Speculative or rumor-based reporting with no corroboration
- News that is old, already resolved, or superseded by more recent updates

## How to reason about it

1. Read the actual content of each result, not just its headline — headlines are
   often more dramatic than the underlying story.
2. Weigh recency — a red flag from 18 months ago that was already resolved is not
   the same as one breaking this week.
3. Weigh corroboration — a single low-quality source alleging something is weaker
   evidence than multiple independent, reputable sources reporting the same fact.
4. If nothing found rises to a genuine red flag, say so plainly. "No concerning
   news found" is a legitimate, honest conclusion — not a failure to find something.

## Output

State your judgment directly: name the specific concern(s) found and why they
matter, or state plainly that no genuine red flags were found in the available
results. Don't hedge with vague language like "some news may raise questions" —
be concrete about what you found and why it does or doesn't matter.
