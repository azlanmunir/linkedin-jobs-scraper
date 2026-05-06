# LinkedIn Jobs Market Intelligence: Key Insights

Run: `market_us_tech_full_20260502`

## Data Basis

- 59,506 raw listing snapshots were collected.
- 7,354 canonical jobs remained after deduping by LinkedIn job ID.
- All role, city, seniority, company, and AI/ML estimates below count each canonical job once.
- The run covers selected US tech hubs over the configured 7-day window: SF Bay Area, New York, Boston, Seattle, and Austin.

## Executive Read

The market is still mainly an engineering and senior-experience market. Dedicated AI/ML roles are real but not dominant: they are 7.5% of deduped jobs, or 6.1% on the weighted estimate. The stronger signal is horizontal AI diffusion: explicit AI/ML/LLM language appears in 56% of job titles or descriptions, including software, product, data, infrastructure, security, and management roles.

Junior hiring is extremely thin. Entry plus intern roles are only 107 of 7,354 jobs, or 1.5% raw. Even in SWE, junior roles are only 2.2%; in AI/ML, 2.9%. This market is asking mostly for mid, senior, staff, manager, and director-level people.

## Market Shape

| Macro area | Jobs | Share |
|---|---:|---:|
| Engineering / Infrastructure | 2,496 | 33.9% |
| Product / Program / Leadership | 2,056 | 28.0% |
| AI / Data / Research | 1,553 | 21.1% |
| Residual Other / Design | 717 | 9.7% |
| Non-core / search leakage | 400 | 5.4% |
| Customer-facing technical | 132 | 1.8% |

Weighted estimates tell the same broad story: engineering/infrastructure is 34.3%, product/program/leadership is 28.7%, and AI/data/research is 17.7%.

## Role Demand

| Role family | Jobs | Share |
|---|---:|---:|
| SWE | 1,405 | 19.1% |
| Management | 876 | 11.9% |
| Program | 722 | 9.8% |
| Other | 692 | 9.4% |
| AI/ML | 553 | 7.5% |
| Product | 442 | 6.0% |
| Data Engineering | 372 | 5.1% |
| Infrastructure/Platform | 309 | 4.2% |
| Security | 274 | 3.7% |
| DevOps/SRE | 272 | 3.7% |

SWE remains the largest single bucket. Product, program, and management together are larger than pure SWE, which suggests a mature market where execution coordination and technical leadership are heavily represented.

## AI/ML Reality Check

- Dedicated AI/ML jobs: 553 of 7,354, or 7.5%.
- Weighted AI/ML estimate: 6.1%.
- AI/ML bootstrap confidence interval in the report: 6.9% to 8.1% raw.
- Explicit AI/ML/LLM language appears in 4,122 postings, or 56.1%.

The interpretation: AI/ML is not the whole market, but AI language has become a broad requirement layer. AI appears in SWE, product, data, infra, security, research, and management jobs, not only in roles titled “Machine Learning Engineer.”

## City Differences

| City | Jobs | AI/ML jobs | AI/ML share | AI/Data/Research share |
|---|---:|---:|---:|---:|
| SF Bay Area | 2,551 | 228 | 8.9% | 22.7% |
| Seattle | 1,059 | 88 | 8.3% | 23.2% |
| New York | 1,590 | 109 | 6.9% | 23.1% |
| Boston | 1,179 | 74 | 6.3% | 18.0% |
| Austin | 975 | 54 | 5.5% | 15.3% |

SF Bay Area has the strongest pure AI/ML share. Seattle and New York are nearly as strong when broader AI/data/research roles are included. Austin is more classic SWE/product/program in this sample.

## Seniority Pressure

| Seniority | Jobs | Share |
|---|---:|---:|
| Mid | 3,464 | 47.1% |
| Senior | 1,837 | 25.0% |
| Manager | 876 | 11.9% |
| Staff+ | 586 | 8.0% |
| Director+ | 468 | 6.4% |
| Entry | 98 | 1.3% |
| Intern | 9 | 0.1% |

This is the most actionable finding for job seekers: the public tech-job market in this sample is overwhelmingly experienced-hire oriented. Entry-level demand is barely visible.

## Company Concentration

- 2,612 distinct companies appear in the deduped corpus.
- Top 10 companies account for 1,018 jobs, or 13.8%.
- Top 25 companies account for 1,541 jobs, or 21.0%.

Top companies overall:

| Company | Jobs |
|---|---:|
| PwC | 204 |
| NVIDIA | 186 |
| Amazon | 115 |
| Google | 100 |
| Alignerr | 80 |
| OpenAI | 78 |
| Visa | 73 |
| Amazon Web Services (AWS) | 71 |
| Adobe | 57 |
| Uber | 54 |

The market is fragmented. Big tech matters, but consultancies, marketplaces, staffing-like firms, and AI-data vendors are also prominent.

## Workplace Mode

| Workplace signal | Jobs | Share |
|---|---:|---:|
| Unknown | 3,979 | 54.1% |
| Hybrid | 1,788 | 24.3% |
| Remote | 921 | 12.5% |
| On-site | 666 | 9.1% |

Among postings with a known workplace signal, hybrid is the dominant mode. Remote is present, but not the default.

## Skills And Platform Signals

Share of postings where the term appears in title or description:

| Signal | Jobs | Share |
|---|---:|---:|
| AI/ML/LLM explicit | 4,122 | 56.1% |
| Python | 2,712 | 36.9% |
| Security | 2,382 | 32.4% |
| AWS | 1,590 | 21.6% |
| SQL | 1,372 | 18.7% |
| JavaScript/TypeScript/React/Node | 1,071 | 14.6% |
| Azure | 1,033 | 14.0% |
| Kubernetes | 966 | 13.1% |
| GCP | 904 | 12.3% |
| Java | 831 | 11.3% |

The stack signal is practical: Python, cloud, SQL, security, and distributed infrastructure show up repeatedly. AI demand seems tied to production software and infrastructure, not just modeling.

## Bottom Line

The original purpose was to understand where the tech job market actually is, especially whether AI/ML demand is real. The answer from this run is:

1. AI/ML is real but not dominant as a standalone role family.
2. AI is becoming horizontal across many job families.
3. Core SWE remains the largest single bucket.
4. The market strongly favors experienced candidates.
5. SF Bay Area leads in pure AI/ML; Seattle and New York are strong in broader AI/data/research.
6. The market is fragmented across thousands of employers; it is not only Big Tech.
7. Hybrid is the leading known work mode, while workplace mode is often unstated.
