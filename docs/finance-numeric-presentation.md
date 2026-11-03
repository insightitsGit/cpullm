# Structured finance request and ratio presentation contract

Structured finance requests are owned by the selected finance specialist before
generic reference resolution. Ownership requires a selected product/action and
JSON or recognized labeled fields; a product definition question stays on the
ordinary factual path. Incomplete payloads reach the specialist's input checks.
The raw-prompt guard and caller authorization remain ahead of that boundary.
Corpus spelling suggestions do not rewrite specialist-owned payloads.

LedgerCovenant makes ratio decisions at the existing six-decimal integer scale.
Presentation preserves those exact stored decision values, including the
threshold. `ratio_places` (JSON) or `ratio places:` (labeled input) accepts 0–6.
The recognized instruction `Show the computed ratio to six decimal places`
also selects six places; equivalent zero–six number words/digits are supported.
Conflicting recognized precision requests are refused. Unrecognized prose is
not a general-purpose numeric-format parser.

The default minimum is two places. More places are automatically shown when
needed to preserve either stored decision value. Thus a requested/default two
places cannot hide `4.500001 > 4.500000`. Requested precision is a minimum,
not permission to erase the digits that determined the verdict. No new rounding
occurs during that display expansion; the existing input division policy still
determines the six-place decision value. This does not create arbitrary-precision
financial reasoning beyond the declared scale.

For example, numerator `9000001`, denominator `2000000`, threshold `4.50` with
the default half-up division produces stored ratio `4.500001` and a breach for
`lte`. Both values are displayed at six places. An exact `4.5` can remain `4.50x`
by default or `4.500000x` when six places were requested.

Tests cover direct components and ordinary `Appliance.ask`, including explicit
and inferred finance selection, incomplete requests and zero denominators.
