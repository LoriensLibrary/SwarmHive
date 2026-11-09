| model | lookup rule | family | compact | lookup arm | lookup taken | delta (compact minus lookup) | Tango 95% | NI at -0.10 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| gemma-4-31b-it | required | V6 | 59/60 | 60/60 | 60/60 | -0.017 | [-0.089, +0.045] | holds (p 0.0157) |
| gemma-4-31b-it | required | V11 | 60/60 | 60/60 | 60/60 | +0.000 | [-0.060, +0.060] | holds (p 0.00491) |
| deepseek-v4-flash | optional (as frozen) | V6 | 60/60 | 51/60 | 47/60 | +0.150 | [+0.081, +0.261] | holds (p 2.23e-05) |

| model | lookup rule | settled pairs | Hodges-Lehmann, lookup minus compact tokens | sign test p |
| --- | --- | --- | --- | --- |
| gemma-4-31b-it | required | 119 | +724 | 3.01e-36 |
| deepseek-v4-flash | optional | 57 | +1971 | 1.39e-17 |

| cohort | registered | complete | errors or invalid | unsafe proposals | gate rejections | unsafe commits | settled | retained | ceiling | complete run |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| v2_gemma431bit_mandlookup | 240 | 239 | 1 | 0 | 0 | 0 | 0.0769 | 0.0251 | 1.0 | yes |
| v2_deepseekv4fl_repV6 | 120 | 114 | 6 | 4 | 3 | 0 | 0.1728 | 0.1422 | 1.5 | yes |
