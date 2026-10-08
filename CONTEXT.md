# Company State Monitor

A research triage tool for people reviewing an IDX watchlist. It describes company changes and presents historical evidence to help decide which financial reports deserve closer reading.

## Language

**Company State**:
A descriptive classification of a company's fundamentals, sector-relative price behavior, and foreign flow at a quarterly information-availability date. A state describes observed conditions independently of whether its historical pattern predicts subsequent returns.
_Avoid_: Recommendation, predictive signal

**Historical Evidence**:
Observations of subsequent outcomes for past company setups evaluated without using those observations to select the setup rules. Evidence supports a historical claim rather than deciding whether a descriptive state exists.
_Avoid_: State confidence, prediction confidence

**Evidence Strength**:
The degree of support for a setup's historical outcome estimate. The submission uses only Weak (exploratory) and Insufficient, separately from outcome direction, state classification, and data availability.
_Avoid_: State confidence

**Outcome Direction**:
Whether a setup's historical outcomes favored, lagged, or resembled its sector. Direction is separate from how well-supported the estimate is.
_Avoid_: Evidence strength

**Neutral**:
A company state for a complete observation that matches none of the named descriptive states. It does not imply an absence of economically notable changes.
_Avoid_: Unknown, missing data

**Unclassified**:
A data-availability status for a company whose available data cannot satisfy the inputs required for state classification.
_Avoid_: Neutral, insufficient evidence

**Stale**:
A freshness status for a previously classified company whose next expected report's availability deadline has passed without usable data. The dated previous state remains part of the company's history.
_Avoid_: Neutral, unclassified

**Pattern Update**:
An assessment of price and foreign-flow changes since a company's latest quarterly state assignment relative to the persistence of that state's descriptive pattern. It can be Strengthening, Stable, Weakening, Contradicting, or Mixed without changing the quarterly state; Neutral has raw changes only.
_Avoid_: Market confirmation, investment outlook, company state transition

**Mixed**:
A Pattern Update label for opposing or inconclusive price and foreign-flow movements relative to the assigned state's pattern.
_Avoid_: Stable

**Completed Outcome**:
A historical observation whose full forward-return period has ended. Only completed outcomes can contribute to historical outcome estimates or to decisions made using those estimates.
_Avoid_: Current setup

**Historical Case**:
A completed historical observation matching the same Company State as the company being examined. Cases need not match a more specific driver pattern.
_Avoid_: Identical setup, nearest neighbor

**Retrospective Research**:
An analysis of past company setups using the historical records currently available. Unless original disclosure dates and data vintages are verified, it does not establish what an investor could have known at the time.
_Avoid_: Historically executable strategy

**Comparable Quarter Earnings**:
Earnings for a standalone quarter compared with the same quarter a year earlier on a consistent accounting basis, in the company's reporting currency. Percentage growth is defined only when the prior comparable quarter has positive earnings; loss transitions and persistent losses are separate conditions.
_Avoid_: Cumulative year-to-date earnings growth, rupiah growth for a US-dollar reporter

**Reference Comparison**:
A historical outcome distribution for a predeclared momentum, earnings-growth, or equal-weight-composite group, presented alongside state outcomes. It is a research reference rather than a condition for assigning a Company State.
_Avoid_: Winning strategy, required predictive hurdle

**Snapshot**:
A dated view of the latest usable company classifications, pattern updates, and historical evidence produced from a particular collection of cached records.
_Avoid_: Live monitor

**Neutral Band**:
The range of a primary dimension treated as neither positive nor negative for state classification. Its boundary is distinct from the Neutral company state, which describes an unmatched complete combination.
_Avoid_: Neutral state threshold

**Information-Availability Date**:
The date a quarterly report is treated as usable for a company observation, identified as actual or estimated. An estimated date does not establish when the original financial figures were publicly known.
_Avoid_: Filing date when estimated

**Sector-Relative Return**:
A company's return less the median return of eligible other companies in its reference group over the same period. The reference is its sector, or the rest of the Study Universe (LQ45-relative) when the sector has too few eligible companies; each measure names its reference, and a later comparison keeps the one recorded with the state. The stated return convention distinguishes price changes from returns including dividends.
_Avoid_: Market-relative return, mixing references in one comparison

**Study Universe**:
The current LQ45 constituents considered over their available history. Historical outcomes for this population describe current constituents rather than the historical performance of an LQ45 investment strategy.
_Avoid_: Historical LQ45 portfolio
