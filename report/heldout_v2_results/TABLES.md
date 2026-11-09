Both cohorts were frozen and run after the preregistered set had been analyzed and this report drafted, to test the two readings a reviewer would challenge first: new seeds, new freezes, separate ledgers, never pooled with the held-out set, same gate, scorer, budget and caps; tables in Appendix B.10.

**Does the gemma-31 gap close when the lookup is required?** The frozen rule let the model "decide directly if the supplied information suffices" and gemma-4-31b-it took the lookup in 13 of 120 offers; the follow-up requires the lookup as the first reply. Under that rule gemma-4-31b-it took the lookup in 120 of 120 offers and completed 120 of 120 same-number cases in the lookup arm against 119 of 120 with preloaded lineage (V6: compact minus lookup -0.017, Tango 95% [-0.089, +0.045]; V11: +0.000, [-0.060, +0.060]). On new instances this supports the optional wording as the cause of the 51-case gap; it does not prove it was the only cause. Cost moved the other way: with the lookup required, the lookup arm spent a Hodges-Lehmann 724 tokens more per settled pair than compact over 119 pairs, so preloading is the cheaper way to deliver the same records.

**Does the marginal DeepSeek V6 claim replicate?** The preregistered V6 claim held at one-sided p 0.043. An independent cohort of 60 new V6 instances: compact 60/60, lookup arm 51/60 (lookup taken 47/60), compact minus lookup +0.150, Tango 95% [+0.081, +0.261], non-inferiority at -0.10 holds (one-sided p 2.23e-05); the lookup arm spent a Hodges-Lehmann 1971 tokens more per settled pair than compact. Of the lookup arm's 9 misses, 3 are among the 7 slots where the model decided without taking the lookup, 0 took the lookup and still missed, and 6 are provider errors. The same model at temperature 0 took the lookup in 59 of 60 offers on the preregistered V6 instances and in 47 of 60 here, so whether an offered lookup is taken varies with the instance set as well as the model, and preloading does not depend on it. The two DeepSeek cohorts are reported side by side and not pooled.

| model | lookup rule | family | compact | lookup arm | lookup taken | delta (compact minus lookup) | Tango 95% | NI at -0.10 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| gemma-4-31b-it | required | V6 | 59/60 | 60/60 | 60/60 | -0.017 | [-0.089, +0.045] | holds (p 0.0157) |
| gemma-4-31b-it | required | V11 | 60/60 | 60/60 | 60/60 | +0.000 | [-0.060, +0.060] | holds (p 0.00491) |
| deepseek-v4-flash | optional (as frozen) | V6 | 60/60 | 51/60 | 47/60 | +0.150 | [+0.081, +0.261] | holds (p 2.23e-05) |

| model | lookup rule | settled pairs | Hodges-Lehmann, lookup minus compact tokens | exact two-sided sign test p |
| --- | --- | --- | --- | --- |
| gemma-4-31b-it | required | 119 | +724 | 3.01e-36 |
| deepseek-v4-flash | optional | 57 | +1971 | 1.39e-17 |

| cohort | registered | complete | errors or invalid | unsafe proposals | gate rejections | lineage-invalid commits | metered | reserves kept | ceiling | complete run |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| v2_gemma431bit_mandlookup | 240 | 239 | 1 | 0 | 0 | 0 | 0.0518 | 0.0251 | 1.0 | yes |
| v2_deepseekv4fl_repV6 | 120 | 114 | 6 | 4 | 3 | 0 | 0.0306 | 0.1422 | 1.5 | yes |
