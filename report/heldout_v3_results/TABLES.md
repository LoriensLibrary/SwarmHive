**Second surface template (post-hoc): completion, lookup use, gate outcomes.**

| model | family | registered per arm | not yet run | compact complete | lookup arm complete | lookup taken | delta (compact minus lookup, registered denominator) | Tango 95% | NI at -0.10 | unsafe proposals | lineage-invalid commits |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| gemma-4-31b-it | V6 | 30 | 0 | 30/30 | 15/30 | 0/30 | +0.500 | [+0.330, +0.668] | holds (p 3.87e-06) | 15 | 0 |
| gemma-4-31b-it | V11 | 30 | 0 | 30/30 | 16/30 | 2/30 | +0.467 | [+0.300, +0.639] | holds (p 6.93e-06) | 14 | 0 |
| deepseek-v4-flash | V6 | 30 | 0 | 30/30 | 24/30 | 24/30 | +0.200 | [+0.064, +0.373] | holds (p 0.000783) | 2 | 0 |
| deepseek-v4-flash | V11 | 30 | 0 | 30/30 | 30/30 | 30/30 | +0.000 | [-0.114, +0.114] | holds (p 0.0339) | 0 | 0 |

| cohort | registered | complete | unsafe proposals | gate rejections | lineage-invalid commits | metered | ceiling | complete run |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| v3_gemma431bit_incidents | 120 | 120 | 29 | 29 | 0 | 0.0199 | 0.6 | yes |
| v3_deepseekv4fl_incidents | 120 | 116 | 2 | 2 | 0 | 0.0238 | 1.5 | yes |
