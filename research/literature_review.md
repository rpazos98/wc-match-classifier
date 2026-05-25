# Literature Review: Predicting Match Interest and Excitement

## 1. Foundational Theory: Uncertainty of Outcome Hypothesis (UOH)

### Seminal Works

- **Rottenberg (1956)** "The Baseball Players' Labor Market" — first articulated that fans prefer contests with uncertain outcomes and that competitive balance is essential for league health.
- **Neale (1964)** "The Peculiar Economics of Professional Sports" — extended the argument to league-level competitive balance.
- **Cairns, Jennett & Sloane (1986)** — distinguished multiple dimensions of uncertainty:
  - **Match-level** (short-run): will this game be close?
  - **Seasonal** (medium-run): is the title race/relegation battle alive?
  - **Long-run** (across seasons): do the same teams always win?

### Empirical Status

Six decades of empirical research have produced **mixed and often conflicting results**. Many studies, especially in European football, fail to find strong evidence that match-level outcome uncertainty drives attendance or TV viewership. Championship/relegation uncertainty (seasonal) tends to find more support than individual match uncertainty.

### Sources
- Competitive Balance in Team Sports — University of Antwerp (repository.uantwerpen.be/docman/irua/f5f467/24751a77.pdf)
- The Uncertainty-of-Outcome Hypothesis and Competitive Balance in Sports (d-nb.info/1138284831/34)
- Measurement of Competitive Balance and Uncertainty of Outcome — University of Otago (otago.ac.nz/__data/assets/pdf_file/0023/324392/measurement-of-competitive-balance-and-uncertainty-of-outcome-076646.pdf)

---

## 2. Match Quality vs. Outcome Uncertainty

A major empirical finding: **team quality matters more than closeness**.

### Key Papers

**Buraimo & Simmons (2015)** "Uncertainty of Outcome or Star Quality? Television Audience Demand for English Premier League Football" — International Journal of the Economics of Business.
- Used 8 seasons of EPL TV data.
- Outcome uncertainty had **zero effect** on TV audiences in later seasons.
- **Star quality** was a significant driver of viewership.
- DOI: 10.1080/13571516.2015.1010282

**Buraimo & Simmons (2008)** "Do Sports Fans Really Value Uncertainty of Outcome?"
- Found that fans' preferences lean toward quality over uncertainty.
- Challenged the core assumption of UOH.

**Cox (2023)** "Stadium attendance demand in the men's UEFA Champions League: Do fans value sporting contest or match quality?" — PLOS ONE.
- Analyzed **1,234 UCL matches (2009-2019)** across 32 nations.
- Outcome uncertainty and competitive intensity were **not significantly associated** with higher attendances.
- **Team quality** and **star players** were significant positive drivers.
- DOI: 10.1371/journal.pone.0276383

### Implication for Our Classifier
Team quality/prestige/ranking deserves significant weight. Pure "closeness" between teams is less predictive of interest than the absolute quality of teams involved. A match between two top-10 teams is more interesting than a close match between two mediocre teams.

---

## 3. Match Significance / Stakes

### Key Papers

**Jennett (1984)** "Attendances, Uncertainty of Outcome and Policy in Scottish League Football"
- Pioneered explicit measurement of match significance.
- Measured whether a team is still in contention for a prize.
- Found championship significance positively affects attendance.

**Buraimo & Forrest (2025)** "Big Games: The Importance of Match Significance for Attendances in Four European Football Leagues" — SSRN Working Paper.
- Argued prior studies failed to find significance effects because they used **ad hoc metrics**.
- Used analytics-rooted metrics: whether winning vs. losing changes the probability of an end-of-season prize.
- Found significant effects on attendance across four leagues.
- A match is deemed significant if its result changes the probability of winning a title, qualifying for Europe, or avoiding relegation.
- **Multi-prize league structure matters**: title race, Champions League qualification, Europa League, and relegation battles all create significance.
- SSRN: 5244551

**Forrest & Simmons (2006)** "New Issues in Attendance Demand" — Journal of Sports Economics.
- DOI: 10.1177/1527002504273392

### Implication for Our Classifier
Tournament stage and elimination context are strong predictors. A group stage match where both teams are already qualified/eliminated is less interesting than one where advancement is at stake. Knockout rounds inherently have maximum stakes. This is one of the most robustly supported factors in the literature.

---

## 4. Suspense and Surprise Theory

### Key Paper

**Ely, Frankel & Kamenica (2015)** "Suspense and Surprise" — Journal of Political Economy.
- Formal economic model of entertainment utility derived from information revelation.
- **Suspense** = variance of next period's beliefs (will things change?). High suspense when outcome is genuinely uncertain and about to be resolved.
- **Surprise** = distance between current and previous beliefs (something unexpected happened). High surprise when an unlikely event occurs.
- Applied to sports, mystery novels, game shows, casinos.
- **This is the most rigorous theoretical framework** for why uncertain contests are entertaining.
- Key insight: entertainment comes not from the outcome itself but from the **process of uncertainty resolution**.
- DOI: 10.1086/677350

**Konjer, Nuesch & Theiler (2024)** "Exploring Entertainment Utility from Football Games" — Journal of Economic Behavior & Organization.
- Directly applies the Ely-Frankel-Kamenica framework to football.
- Examines the role of **belief dynamics** for entertainment utility.
- Models how fans derive entertainment from the information process of watching a match.
- DOI: 10.1016/j.jebo.2024.04.016 (ScienceDirect: S0167268124001537)

### Implication for Our Classifier
Pre-match suspense can be estimated from the variance of possible outcomes. Matches where multiple outcomes are plausible (group stages with complex qualification scenarios, evenly-matched knockout ties) offer higher suspense. Surprise is harder to predict pre-match but relates to upset potential — matches where a lower-ranked team has a non-trivial chance of winning offer surprise potential.

---

## 5. Probabilistic Excitement: Win Probability Dynamics

### Key Papers

**Vecer (2007)** "On Probabilistic Excitement of Sports Games" — Journal of Quantitative Analysis in Sports.
- Defines excitement as the **total variation of the win probability** during a match.
- Uses a Poisson scoring model for soccer.
- Key results:
  - Higher scoring rates lead to more excitement.
  - The most exciting games occur when the opponent is **slightly stronger** (not equal).
  - Given total scoring rate, **closer teams** = more exciting.
  - Asymmetry: slight favorite vs. slight underdog produces more variation than 50-50.
- Applied to 2006 World Cup using betting market data.
- Available: stat.berkeley.edu/~aldous/157/Papers/excitement.pdf

**Game Excitement Index (GEI)** — used by FiveThirtyEight and ESPN.
- Sums the absolute value of win probability changes across plays/events.
- Normalized so overtime games aren't automatically rated higher.
- Post-hoc metric (requires match to be played).
- Reference: sports.sites.yale.edu/game-excitement-index-part-ii

**Stern & Alberg (2020)** "Having a Ball: Evaluating Scoring Streaks and Game Excitement Using In-Match Trend Estimation"
- Proposes the **Excitement Trend Index (ETI)**: the expected number of monotonicity changes in the running score difference.
- Uses latent Gaussian processes to model score differences.
- Applied to NBA to cluster teams by how exciting they are to watch.
- arXiv: 2012.11915

### Implication for Our Classifier
Vecer's finding is particularly relevant: the optimal excitement is when one team is a **slight underdog**, not when teams are exactly equal. This suggests our closeness metric should not simply maximize at 50-50 but should have a slight asymmetry. Pre-match, we can estimate expected win probability variation using team strengths and expected goal rates.

---

## 6. Scoring Dynamics, Lead Changes, and Comebacks

### Key Papers

**Clauset, Kogan & Redner (2015)** "Safe Leads and Lead Changes in Competitive Team Sports" — arXiv: 1503.03509.
- Analyzed the statistical structure of lead changes across sports.
- Lead changes (when score difference crosses zero) identified as peak excitement moments.
- Different sports have different lead-change dynamics depending on scoring frequency.

**Football Match Dynamics** — Frontiers in Psychology (2021).
- Explored football match dynamics through recurrence analysis.
- Bursty goal-scoring dynamics: the same team is more likely to score again shortly after a previous goal (momentum effect).
- DOI: 10.3389/fpsyg.2021.747058

### Implication for Our Classifier
Pre-match, we can estimate lead-change probability from expected goals and team strengths. Matches with higher expected combined goals and closer teams will have more expected lead changes. Low-scoring matches (e.g., two defensive teams) may be less exciting even if close.

---

## 7. Betting Odds as Proxy for Uncertainty

### Key Papers

**Forrest & Simmons (2002)** "Outcome Uncertainty and Attendance Demand in Sport: The Case of English Soccer" — Journal of the Royal Statistical Society, Series D.
- Pioneered using betting odds as a measure of outcome uncertainty in football.
- Modeled the betting market to identify inefficiency, then adjusted odds.
- Found admissions relate **positively to team quality** and **negatively to relative win probabilities** (supporting UOH at match level).
- DOI: 10.1111/1467-9884.00329

**Peel & Thomas (1988, 1992)** — earlier foundational work using odds in English soccer demand models.

**Cain, Law & Peel (2000)** "A Comment on the Bias of Probabilities Derived From Betting Odds"
- Cautioned that normalized betting odds **diverge systematically from true probabilities**.
- **Favorite-longshot bias**: longshots are overbet (odds too short), favorites are underbet (odds too long).
- Implied probabilities from odds require adjustment (e.g., Shin method, power model) before use as true probability estimates.

### Implication for Our Classifier
If using betting odds to derive match closeness, we need to be aware of the favorite-longshot bias. Raw implied probabilities from odds overstate the chance of upsets. For a World Cup context, we may be better served by ELO-derived probabilities or model-based estimates than raw betting odds.

---

## 8. TV and Digital Demand Determinants

### Key Papers

**Schreyer, Schmidt & Torgler (2017, 2018)** — Multiple papers on German TV demand for football.
- Found a **significant positive relation** between TV demand and game outcome uncertainty for both Bundesliga and EPL broadcasts in Germany.
- DOI (2018): 10.1111/geer.12120

**Petersen-Wagner, Gasparetto & Addesa (2025)** "Watching Football Highlights on YouTube" — European Sport Management Quarterly.
- Analyzed **2,268 YouTube highlight videos**.
- Model explains **89% of demand variance**.
- Key findings on event-level excitement drivers:
  - **Red cards**: +5.13% views per occurrence
  - **Own goals**: +11.2% views per occurrence
  - **Penalty kicks**: no significant effect
  - **Total goals**: positive effect on views
- DOI: 10.1080/16184742.2025.2537653

**Factors affecting audience demand for professional football game videos (2025)** — Humanities and Social Sciences Communications (Nature).
- Complementary research on post-game highlight consumption on streaming platforms.
- DOI: 10.1038/s41599-025-04587-4

### Implication for Our Classifier
These studies validate that dramatic in-match events (red cards, own goals) significantly boost post-match interest. While we can't predict these pre-match, teams with higher disciplinary records or defensive vulnerability could be flagged as having higher "drama potential."

---

## 9. Willingness to Pay for Competitive Balance

### Key Papers

**Pawlowski & Budzinski (2013)** "The Monetary Value of Competitive Balance for Sport Consumers" — SSRN: 2163095.
- Used stated preference approach across Germany, Denmark, Netherlands.
- Danish fans willing to pay 160% more than German/Dutch fans (5 EUR vs 3 EUR) for increased competitive balance.

**Nalbantis, Pawlowski & Coates (2017)** "The Fans' Perception of Competitive Balance and Its Impact on Willingness-to-Pay for a Single Game" — Journal of Sports Economics.
- **Perceived** competitive balance (not objective measures) drives willingness to pay.
- Subjective assessment of match closeness matters more than statistical measures.
- DOI: 10.1177/1527002515588137

**Budzinski & Pawlowski (2017)** "The Behavioral Economics of Competitive Balance"
- Uncertainty of outcome increases marginal utility and drives WTP.
- DOI: 10.1177/155862351701200203

### Implication for Our Classifier
Perception matters. A match perceived as close (based on team narratives, recent form, media attention) may generate more interest than one that is statistically close but perceived as one-sided. This supports incorporating "narrative" factors beyond pure statistical closeness.

---

## 10. Rivalry and Derby Effects

### Key Papers

**Tyler, Morehead, Cobbs & DeSchriver (2024)** "What is rivalry? Old and new approaches to specifying rivalry in demand estimations" — SSRN.
- Argues that measurement methodology explains why some studies find strong rivalry effects and others do not.
- No uniform definition of "rivalry" across the literature.
- DOI: 10.2139/ssrn.4988545

Research on rivalry effects is **mixed**:
- Derbies generally increase broadcast demand in some contexts.
- Some studies find no effect (e.g., EPL TV viewership, MLS attendance).
- The inconsistency stems from how "rivalry" is defined and measured.

### Implication for Our Classifier
Historical head-to-head record and known rivalries (e.g., Argentina-Brazil, Germany-Netherlands) can boost interest, but this is hard to systematize. A curated rivalry database or historical matchup frequency could serve as a feature, but shouldn't be overweighted given the mixed evidence.

---

## 11. Tournament Design and Attractiveness

### Key Papers

**Scarf & Yusof (2011)** "A numerical study of tournament structure and seeding policy for the soccer World Cup Finals" — Statistica Neerlandica.
- Used simulation to study how seeding affects the probability of best teams advancing and overall tournament attractiveness.
- DOI: 10.1111/j.1467-9574.2010.00471.x

**Csato (2025)** "Tournament design: A review from an operational research perspective" — European Journal of Operational Research.
- Comprehensive survey classifying papers by design criteria:
  - **Efficacy**: do the best teams advance?
  - **Fairness**: are teams treated equally?
  - **Attractiveness**: are matches interesting to watch?
- Attractiveness as explicit design criterion for tournaments.

### Implication for Our Classifier
Tournament structure itself affects match interest. World Cup knockout matches are inherently more interesting due to single-elimination stakes. Group stage matches vary depending on qualification scenarios. Our stage-based weighting is supported by this literature.

---

## Synthesis: Validated Factors Ranked by Evidence Strength

| Factor | Evidence | Key Papers | Mechanism |
|--------|----------|------------|-----------|
| **Team quality / star players** | Strong | Buraimo & Simmons 2015, Cox 2023 | Fans want to see the best |
| **Match significance (stakes)** | Strong | Jennett 1984, Buraimo & Forrest 2025 | Consequences elevate interest |
| **Scoring dynamics (expected goals)** | Strong | Vecer 2007, Stern & Alberg 2020 | More goals = more win probability swings |
| **Outcome uncertainty (closeness)** | Mixed | UOH literature, 60 years | Theoretically sound, empirically inconsistent |
| **Surprise events (red cards, own goals)** | Moderate | Petersen-Wagner 2025 | Unusual events drive engagement |
| **Rivalry / derby** | Mixed | Tyler et al. 2024 | Context-dependent, hard to measure |
| **Competitive balance (season-level)** | Moderate | Pawlowski & Budzinski 2013 | Season-long uncertainty > match-level |
| **Higher expected scoring rate** | Moderate | Vecer 2007 | More scoring opportunities = more excitement |
| **Comeback potential** | Moderate | Clauset et al. 2015 | Lead changes are peak excitement |

## Key Theoretical Frameworks for Pre-Match Prediction

1. **Uncertainty of Outcome Hypothesis** (Rottenberg 1956) — classic but empirically contested at match level
2. **Suspense and Surprise** (Ely, Frankel & Kamenica 2015) — most rigorous formal entertainment model
3. **Win Probability Total Variation** (Vecer 2007) — quantitative excitement metric, can be estimated pre-match
4. **Excitement Trend Index** (Stern & Alberg 2020) — monotonicity changes in score difference
5. **Game Excitement Index** (FiveThirtyEight) — sum of absolute win probability changes (post-hoc)

## Non-Obvious Insights

1. **Optimal excitement is NOT at 50-50**: Vecer (2007) shows the most exciting match is when the opponent is **slightly stronger**. Perfect balance is not the peak.

2. **Quality > closeness**: Multiple studies show fans prefer watching great teams over close matches between mediocre ones. Brazil vs Argentina is more interesting than Ecuador vs Bolivia even if the latter is "closer."

3. **Perceived closeness > actual closeness**: Nalbantis et al. (2017) found subjective perception of competitiveness drives interest more than objective statistical measures.

4. **Stakes are robust, uncertainty is not**: Match significance is one of the most consistently supported factors across studies, while pure outcome uncertainty produces conflicting results.

5. **Favorite-longshot bias**: Raw betting odds overstate upset probability. Any odds-based closeness measure needs correction (Cain et al. 2000).

6. **YouTube data validates drama**: Red cards (+5.13%) and own goals (+11.2%) significantly increase highlight viewership (Petersen-Wagner 2025). Goals matter, but dramatic events matter more per occurrence.
