**Second surface template (post-hoc): completion, lookup use, gate outcomes.**

| model | family | compact | lookup arm | lookup taken | delta (compact minus lookup) | Tango 95% | NI at -0.10 | unsafe proposals | unsafe commits |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| gemma-4-31b-it | V6 | 30/30 | 15/30 | 0/30 | +0.500 | [+0.330, +0.668] | holds (p 3.87e-06) | 15 | 0 |
| gemma-4-31b-it | V11 | 30/30 | 16/30 | 2/30 | +0.467 | [+0.300, +0.639] | holds (p 6.93e-06) | 14 | 0 |
| deepseek-v4-flash | V6 | 11/11 | 9/11 | 9/11 | +0.067 | [-0.054, +0.213] | holds (p 0.00921) | 1 | 0 |
| deepseek-v4-flash | V11 | 10/10 | 11/11 | 11/11 | -0.033 | [-0.167, +0.084] | fails (p 0.112) | 0 | 0 |

| cohort | registered | complete | unsafe proposals | gate rejections | unsafe commits | settled | ceiling | complete run |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| v3_gemma431bit_incidents | 120 | 120 | 29 | 29 | 0 | 0.0199 | 0.6 | yes |
| v3_deepseekv4fl_incidents | 120 | 42 | 1 | 1 | 0 | 0.0562 | 1.5 | RUNNING |
