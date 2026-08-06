# LongMemEval adjacent-comparison correction

The manuscript previously described the LongMemEval Holm family as six tests.
Direct recomputation from the five systems' 180 paired judgment rows shows that
the displayed adjusted p-values are the Holm adjustment for the four
predeclared adjacent comparisons in the reported ordering.

| Adjacent comparison | b | c | Raw exact p | Holm p (m=4) |
|---|---:|---:|---:|---:|
| B3 recency vs B1 no memory | 34 | 0 | 1.164153218e-10 | 4.656612873e-10 |
| B2 flat vector vs B3 recency | 48 | 11 | 1.241628226e-6 | 3.724884679e-6 |
| B4 naive overwrite vs B2 flat vector | 44 | 10 | 3.385685953e-6 | 6.771371907e-6 |
| ASK vs B4 naive overwrite | 31 | 8 | 2.940768754e-4 | 2.940768754e-4 |

The correction changes the family-size wording, not any displayed adjusted
p-value or the ASK-versus-B4 conclusion. The historical derived analysis report
is preserved; `artifacts/analysis/lme_v12_adjacent_mcnemar.json` is the
authoritative additive correction.
