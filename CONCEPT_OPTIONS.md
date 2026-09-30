# Four concepts for the KBC case, pick one by 19:35

Same brief, four different answers to "a new way KBC understands, supports and guides its customers". They differ on the axis of personalization:

| | A. Kate Foresight | B. Kate Autopilot | C. Financial Immune System | D. Personal Economist |
|---|---|---|---|---|
| Axis | **Time**: anticipate what is about to happen in your life | **Action**: delegate money admin within limits | **Protection**: notice trouble early, respond in graded steps | **World**: when the rules or the markets change, compute what it means for you |
| Kate's role | Kate gets a calendar | Kate gets a mandate | Kate gets reflexes | Kate reads the Staatsblad so you don't have to |
| Relationship shift | From reacting to anticipating | From advising to acting on your behalf | From selling to protecting | From generic news to your personal impact |
| Hero data | Bank + insurance dates, fiscal calendar | Customer's own instructions, event stream | Anomalies, stress signals, cover gaps | A structured rulebook of law, tax, rate and price changes + a digital twin per customer |
| One-line pitch | "A bank that knows what's next, and shows you why." | "Tell Kate what she may do. She does the rest, and asks when unsure." | "A bank-insurer that notices trouble before you do." | "Belgium changes the rules. KBC tells 2.3 million people what it means for them, overnight." |

Details for A are in `ACTION_PLAN.md` section 6. B, C and D follow, then the MECE tree that generated D, the scoring matrix and the 10-minute decision method.

---

## What the research says the environment rewards (all three build on this)

**KBC's corporate direction (2025–2026).** Strategy "Differently: the Next Level", four cornerstones: customer at the centre, unique bank-insurance experience, sustainable profitable growth, role in society. Kate 2.0 is fully LLM-driven (GPT-4.1), ~75–80% autonomy, 6.2M users group-wide, 1.3M proactive nudges/month in 140+ situations, target 10M conversations in 2026. KBC says it is "exploring agentic AI" but "Kate will never implement anything without explicit customer approval". Named roadmap: advice on **housing, mobility and energy**. Commercial engine: bank-insurance clients 76% → target 83%, "stable" bank-insurance clients 24% → 29%, digital sales 65% bank / 35% insurance. Trust investments: in-house fraud engine on every transaction, Guardian Angel (Feb 2026), 120+ staff handling 1,000+ daily contacts with pressured customers. Ecosystem: Kate Wallet (summer 2026), Kate Coins earn/spend anywhere, Wero, Bolero incl. crypto. Growth: 365.bank (Slovakia) closed Jan 2026, studying insurer Ethias. Belgium first, then Czech Republic and the rest of the group.

**Belgian environment.** Record ~€302bn on savings accounts and only 37% of Belgians invest; new 10% capital-gains tax since Jan 2026; pension bonus/malus reforms; unemployment benefits capped at 24 months since Mar 2026 (~180k people); insurance premiums up (BA ~+5%, hospitalisation +10% on old contracts, insurance tax to 9.6% in April 2026); phishing losses ~€93M in 2025 (+30% cases); Wero replacing Payconiq (Bancontact Pay since Mar 2026); itsme 8M users, MyGov.be becoming the EU identity wallet in 2026; Doccle+Zoomit 4.4M users; Peppol e-invoicing mandatory since Jan 2026; branch closures and Batopin cash points; 8 in 10 Belgians averse to sharing data with third parties (KBC's own survey). Three brands, three languages, regional rules.

**Fintech competitors and what "translating to 2.3M Belgians" means.** Revolut: 1M+ customers in Belgium, Belgian IBANs, AI assistant "AIR" (Apr 2026: spend breakdowns, subscriptions, card controls, biometric approval for sensitive actions, zero data retention, sees only what the customer sees), RevPoints, Pockets, Pay Early, yearly RevReview. Belfius: "Hey Belfius" (Mistral AI, chat + voice, proactive) for 2.2M customers. bunq Finn, N26 rules, Nubank "AI private banker", Klarna's retreat from all-AI support to hybrid. Fintechs win on speed and money-intelligence UX; they lose on trust (Revolut is the UK's most complained-about firm for fraud), human escalation, advice and insurance. Translating any fintech mechanic to KBC's 2.3M means adding what fintechs cannot: bank+insurance context, a human path (KBC Live, 300+ branches), and Belgian rails (itsme, Doccle, Wero). A KBC idea that could be shipped by Revolut next quarter is not a winning idea.

**EU regulation and trends.** AI Act: transparency duties (Art. 50) in force since 2 Aug 2026, high-risk obligations (credit scoring, life/health insurance pricing) delayed to Dec 2027, Art. 5 bans exploiting vulnerability. GDPR: CJEU SCHUFA (2023) and Dun & Bradstreet (2025) require meaningful explanations of automated logic; unconditional right to object to marketing profiling. FiDA (open finance, permission dashboards) stalled but coming ~2028; PSD3/PSR agreed Nov 2025 (~2028): fraud-liability shift to banks, consent dashboards. Instant payments + Verification of Payee since Oct 2025; SEPA Request-to-Pay 2026; digital euro pilot 2027. eIDAS 2.0: identity wallets due end 2026, banks must accept them for authentication from ~2027. European Accessibility Act since Jun 2025. Consumer Credit Directive 2 applies 20 Nov 2026 (forbearance, disclosure of personalised offers, right to human intervention). Savings and Investments Union: savings-and-investment-accounts recommendation of 30 Sep 2025. Trends: agentic commerce (Google AP2 mandates as verifiable credentials, Mastercard Agent Pay and Visa Intelligent Commerce live in Europe, Lloyds' agentic framework across 21M accounts, ING agentic mortgage decisions), voice assistants (ElevenLabs agents, Gemini Live), hyper-personalization at scale (CommBank 55M decisions/day, DBS 1.2bn nudges/year), vulnerability monitoring (NatWest/Serene), tone guardrails (Monzo's "shaming" backlash).

---

## B. Kate Autopilot: mandate-based delegated banking

**One line.** You tell Kate, in plain Dutch or French, what she may do and within which limits. Kate then runs your money admin across bank and insurance automatically, asks when something falls outside the envelope, and shows every action. Personalization becomes understanding what each customer is willing to delegate.

**The twist.** KBC's own rule, "never without explicit approval", becomes the product: approval is given once, bounded, revocable, signed. This is the KBC-compatible form of agentic AI, and agentic is the dominant 2026 banking trend (Lloyds, ING, Belfius "super agents", Revolut AIR, Google AP2 mandates). Nobody in Belgium has shipped natural-language mandates across bank *and* insurance.

**Example mandates (Belgian).**
- "Keep €2,000 on my current account, sweep the rest to savings, but never break my fidelity premium."
- "Pay my Doccle invoices under €150 two days before they are due, only if the payee name matches (Verification of Payee)."
- "If any KBC insurance premium rises more than 5% at renewal, prepare two alternatives and ask me."
- "Top up my pensioensparen to €1,050 in December if my buffer stays above €5,000."
- "Each December, realise gains on Bolero up to the €10,000 capital-gains exemption."
- "My mother (Rita): every new payee above €500 needs my OK first." (KBC's Guardian Angel, generalised.)
- Self-employed: "Pay Peppol supplier e-invoices up to €500 on the due date when cash is above €8,000."

**Why it fits KBC.** Directly extends Kate's autonomy metric (their headline KPI), touches bank + insurance + investing in one layer (moves the 76% → 83% target), reduces workload (FTE-equivalents, another KBC headline), and turns trust into a feature for data-averse Belgians: the customer holds the steering wheel.

**Why it is not a feature.** A mandate layer that every product plugs into (payments, savings, insurance renewals, investing, e-invoices), with one envelope model, one audit log, one exception queue to humans. New mandate types are added without touching the app.

**EU design.** Mandate object = AP2-style signed intent with scope, limits, expiry, revocation (ready for the EU identity wallet in 2026); PSR-style permission dashboard; AI Act Art. 14 human oversight (customer-authored, bank kill switch, disclosure); GDPR Art. 22 satisfied because the customer instructs; VoP check before any automated payment; CCD2: mandates can never take credit.

**Scale to 2.3M.** Mandates are structured `{trigger, condition, action, limits, expiry}` evaluated by an event-driven engine (Pub/Sub); millions of events/day is cheap. The top 20 mandate templates cover most customers. The LLM only compiles natural language into a validated mandate and explains it back; it never moves money. Exceptions become Kate-leads for humans, KBC's existing flow. KPIs: mandates per customer, € automated, exception rate, autonomy rate.

**Tonight's PoC (3 hours).**
1. Mandate compiler: NL/FR/EN sentence → JSON mandate via Gemini with a strict schema and server-side validation (allowed action types, amount caps, no credit, no new payees without approval).
2. Envelope UI: create, review, sign (simulated itsme/biometric), list, pause, revoke, audit log.
3. Event simulator: replay 30 days of events per persona (salary, Doccle invoice, premium increase, balance moves) → executions and "asks".
4. Six mandate templates: sweep, invoice autopay with VoP check, premium watch, pensioensparen top-up, capital-gains harvest, guardian approval.
5. Control room: active mandates across 200 customers, € automated, exceptions routed to humans.
6. Voice: "Kate, keep two thousand and save the rest" → compiled mandate read back by ElevenLabs for confirmation.
7. Security: the limit checks are business logic, exactly what Aikido's audit reasons about. Enforce every limit server-side and unit-test it.

**Demo storyline.** Lien sets the sweep by voice; an energy invoice arrives and is paid after a VoP match; her car premium jumps 9% → Kate prepares two options and asks. Marc (FR) sets the December pension top-up and the capital-gains harvest. Rita's daughter sets the guardian mandate; a suspicious €900 transfer is held for her OK. Control room closes.

**Risks.** "Isn't this standing orders / N26 rules?" → answer with natural language, cross-product, bounded exceptions, audit, and the inverted relationship. The demo must show the "ask" moment, or it feels unsafe. Build risk is higher than A (the compiler and the simulator must both work).

---

## C. Financial Immune System: protective personalization

**One line.** A bank-insurer that notices trouble before you do. Continuous, privacy-preserving sensing of financial stress and threat (fraud, income shock, premium shock, cover gaps, debt creep), with graded, explainable responses from a quiet tip to a human call, across bank and insurance. Personalization becomes the right protection at the right moment.

**The twist.** Every other team will personalize to sell. This personalizes to protect, and the bank-insurer is the only player whose business *is* protection. The immune metaphor gives the architecture: innate reflexes (instant rules: hold, warn), adaptive response (learned per-customer patterns), memory (never repeat a false alarm; learn from feedback), and "fever" = **care mode**, which suppresses all sales nudges while a customer is in difficulty. That last part is the ethical statement that KBC's "role in society" cornerstone is asking for.

**Why now.** Phishing cost Belgians ~€93M in 2025 and PSR will shift more fraud liability to banks, so prevention has hard ROI. CCD2 forbearance duties apply on 20 Nov 2026, seven weeks away. AI Act Art. 5 bans exploiting vulnerability; the mirror image is detecting and protecting it. The unemployment cap since March 2026 hits ~180k households; premiums and energy are up. KBC already runs Guardian Angel and a 120-person team for pressured customers, so this scales what they already believe in. Benchmark: NatWest's early-distress detection with Serene.

**Belgian signals to sense.** VoP "close match" on a new payee at an unusual hour; a first large transfer after a limit increase (the July 2026 Febelfin action plan); salary stops and RVA benefits start; rising minimum payments and subscription creep; hospitalisation premium +11% on an old contract; kinderopvang payments without family liability insurance; energy invoice +30% via Doccle; a renovation-obligation deadline approaching with no renovation spend; a pensioner near a closing branch (Batopin map, universal banking service); regional and language context.

**Why it fits KBC.** Bank + insurance data together reveal cover gaps no bank and no insurer can see alone; the human channel is the response of last resort (KBC Live, branches, Guardian Angel); it strengthens the relationship in the moments that decide loyalty. It also sells protection products honestly (a gap is a real need), which moves the bank-insurance KPI without pushing.

**Why it is not a feature.** A sensing-and-response layer with one resilience score per customer, one graded response policy, one feedback memory, feeding Kate, the app, the fraud team and advisors. Fraud, financial stress and protection gaps are today three separate silos; this is one system.

**EU design.** No health inference (GDPR special categories): only financial signals. Explanations on every alert (SCHUFA/Dun & Bradstreet). Human in the loop for any hold or credit-related step (GDPR Art. 22, AI Act). Care mode = CCD2 forbearance made operational. Voice channel for elderly (Accessibility Act). Decision log (DORA, AI Act).

**Scale to 2.3M.** KBC already scans every digital transaction. Add a nightly resilience score plus streaming detectors; a graded response policy that respects human capacity (the control room shows daily case load per tier, so the 120-person team is never flooded); false-positive rate as a first-class metric. KPIs: fraud losses avoided, arrears prevented, customers reached before a missed payment, Guardian activations, cover gaps closed, NPS in stressed segments.

**Tonight's PoC (3 hours).**
1. Synthetic 12-month streams for the personas with injected "symptoms" (fraud pattern, income drop, premium jump, cover gap, invoice spike).
2. Eight detectors (rules) plus one simple per-customer anomaly score.
3. Resilience score and graded response policy: tier 0 log, tier 1 in-app tip, tier 2 Kate voice/chat, tier 3 human call or Guardian Angel, tier 4 hold.
4. Care mode: toggled by the engine, visibly suppresses sales content; ends when income returns.
5. "Why?" and feedback ("false alarm") that updates the memory.
6. Control room: tiers, case load, false-positive rate, decision log.
7. Voice: the protective call script for Rita in Dutch via ElevenLabs.

**Demo storyline.** Rita: a €900 transfer to a "close match" payee at 22:40 → held, Guardian Angel notified, Kate calls her in Dutch. Marc (FR): hospitalisation premium +11% and a family cover gap after the second child → two options, advisor optional. Lien: contract ended, salary stops → care mode: sales off, budget plan, payment holiday, human advisor; three months later salary returns and care mode lifts. Control room closes.

**Risks.** "Fraud detection exists" → answer with breadth (stress + gaps + fraud in one policy), care mode, graded human response, and ROI. Tone must be impeccable (Monzo lesson). Less obviously "exciting" than A or B; the immune metaphor and care mode carry the originality score.

---

## D. Personal Economist: personalization on the world, not only on the person

**One line.** Every customer gets a digital twin: a structured model of their financial life (income, home, mortgage, cars, policies, savings, investments, family, region). Every night the twin is re-run against the changing Belgian and European rulebook and market conditions. When something changes in the world, each affected customer gets a quantified "what this means for you, and what to do" at the moment it matters: announcement, vote, entry into force, deadline.

**Where it comes from (the MECE cell nobody covers).** Ask "where does a customer's need come from?" and there are exactly four mutually exclusive, collectively exhaustive origins:

1. **What the customer decides** (intentions, instructions) → B.
2. **What happens in the customer's life** (predictable transitions and dates) → A.
3. **What happens to the customer** (fraud, income shock, damage) → C.
4. **What happens around the customer** (laws, taxes, interest rates, prices, indexes, climate rules, KBC's own terms) → nobody. That is D.

Every bank personalizes on the person. Almost nobody personalizes on the world, even though the world is what changed for all 2.3M customers at once in 2026: the 10% capital-gains tax, the pension bonus/malus, the 24-month unemployment cap, company-car deductibility, the insurance tax to 9.6%, hospitalisation index, the renovation obligation relaxed to 6 years, the VerbouwPremie cuts, the Flemish inheritance-tax cuts, the June index jump, Peppol, VoP, Wero, and at EU level the AI Act, CCD2 in November, PSD3, the identity wallet, the digital euro. Today a customer learns about these from newspapers and Test Aankoop, generically. KBC Economics is one of the most cited research teams in Belgium, but it writes for everyone. D makes it write for one person, 2.3 million times.

**The twist.** The trigger is not a customer signal but a rule object. One rule change, one overnight batch, millions of personal, quantified, explainable messages. This is KBC's fifth question ("meaningful impact for millions of customers at the same time") answered literally, and it is counter-intuitive enough to score on originality.

**Examples (all real 2026 changes).**
- "The capital-gains tax starts on 1 January. Based on your Bolero portfolio, your 2026 gains are on track for ~€6,400: under the €10,000 exemption. Nothing to do, unless you sell the ETF you bought in 2019 (photo value applies)."
- "Your company car is a diesel ordered in 2024: 50% deductible this year, 25% next year, 0% in 2028. Your employer's fleet policy will likely change at your lease end (Jan 2027). Here is what an EV lease does to your net pay."
- "Flanders relaxed the renovation obligation: you now have until March 2031, not 2030. Your renovation loan can be spread over one more year."
- "The June index jump raises your pension by 2% from September: +€38/month. Your fidelity premium on the savings account is due on 14 October, so wait until then to move money."
- "From 1 April the insurance tax is 9.6%: +€11 on your car policy. No action, we already applied it."
- "CCD2 applies from 20 November: if your income drops, you have a legal right to a payment plan before any enforcement. We have activated it on your file automatically."
- Self-employed: "Peppol e-invoicing is mandatory since January; 3 of your 12 suppliers still send PDFs. Here is the switch."

**Why it fits KBC.** Cross-product by construction (tax, pension, insurance, mortgage, investing, payments). Bank + insurance data make the twin complete enough to quantify. It builds on KBC Economics (a brand asset) and on Kate's roadmap ("housing, mobility, energy" are exactly where rules change most). It moves bank-insurance and investment KPIs honestly: the action is often a KBC product (Mijn VerbouwLening, pension saving, term account, EV lease insurance). Region and language aware by necessity (Flemish vs Walloon vs Brussels rules).

**Why it is not a feature.** A rulebook + twin + impact engine is a layer: every new law, budget deal, ECB decision or KBC tariff change is one more rule object; the engine, the explanations, the channels and the control room are shared. It also portable to the group: swap the Belgian rulebook for the Czech one.

**EU design.** Fully deterministic and explainable (SCHUFA / Dun & Bradstreet standard met by design). Information about personal impact, with a human advisor one tap away for anything that is investment or credit advice (MiFID / IDD boundary, GDPR Art. 22, AI Act human oversight). AI disclosure on voice. Decision log. No inference of sensitive data: the twin only uses contract and transaction facts.

**Scale to 2.3M.** The rule is one object; the twin is a row per customer; impact = rule applied to row, in BigQuery, minutes for 2.3M. Affected customers are usually a subset (5–40%). The LLM phrases the structured impact in NL/FR/EN; numbers come from the engine. Arbitration and frequency caps as in A. Delivery on the rule's own calendar: announcement (heads-up), entry into force (what changed), deadline (last call). KPIs: customers reached per rule change, actions taken, advisor conversations created (Kate-leads), products opened, and a new one: "time from Staatsblad to customer".

**Tonight's PoC (3 hours).**
1. Rulebook: 8 real 2026 changes encoded as structured rules with effective dates, affected-population predicate and impact formula (capital-gains tax, company-car deductibility, insurance tax, renovation obligation, pension top-up ceilings, index jump for pensioners, unemployment cap, Peppol).
2. Twin: the same synthetic dataset as A (personas + 200 customers) with the fields the rules need.
3. Impact engine: rule × twin → `{affected, € impact, direction, confidence, evidence[], actions[], timing}`.
4. UI: "What changed in the world, and what it means for you" feed with Why? and actions; a "Rules on my horizon" timeline; and the control room where a new rule is dropped in and the engine shows in seconds how many of the 200 customers are affected, the total €, and the channel plan.
5. Narration by Gemini in the customer's language; voice by ElevenLabs.
6. The demo moment: paste a fresh headline ("Government agrees budget: savings-account exemption replaced by €6,000 investment-income exemption") → Gemini drafts the rule object → engineer approves → engine runs → personalised impacts appear for Lien, Marc and Rita.

**Demo storyline.** Marc (FR): company-car rule + insurance tax, routed to an advisor for the EV lease. Lien: capital-gains tax on her ETFs (nothing to do, explained) and the VerbouwPremie cut before she buys. Rita: index jump + fidelity premium timing, delivered by voice. Control room: the budget-headline → rule → 2.3M story.

**Risks.** "It is a newsletter engine" → answer with quantified per-customer € impact, actions, the twin, and the live rule ingestion in the demo. Rules must be encoded correctly: use only the figures in `ACTION_PLAN.md` section 3 and mark anything else illustrative. Advice boundary: phrase as personal impact plus "talk to an advisor", never "you should sell".

---

## The MECE tree behind the four options

Question: how can KBC understand what a customer needs and act at the right moment, at scale?

- **Where does the need originate?** (mutually exclusive, collectively exhaustive)
  - Customer's own decisions and instructions → B
  - Customer's life course: predictable transitions and dates → A
  - Adverse events hitting the customer → C
  - Changes in the customer's environment: law, tax, rates, prices, KBC terms → D
- **How does the bank respond?** inform and explain / recommend / act on behalf / protect and prevent / hand to a human. Each option uses all five, with a different centre of gravity.
- **Through which channel?** app card / Kate chat / Kate voice / advisor call / letter or branch. Same for all four; the engine chooses.
- **At which unit?** individual / household / cohort / whole population. A, B, C are individual; D is population-first, individual-second, which is why it scales differently.

Read the tree top-down and the four options are the complete solution space for "origin of need". That is the line for the video: "Tonight we built one cell. The full engine has four."

## Honourable mentions (one line each, fold into any winner)

- **Glass Bank / Kate's Notebook**: the customer sees and edits the bank's model of them (household, home, car, goals, channel preference) with confidence and evidence; corrections are the strongest signal. Strong trust story, weak demo on its own. Use as the "Why?" and consent layer in A, B or C.
- **Household OS**: personalize the Belgian family, not the individual (joint accounts, kids' accounts, grandparents' gifts under the new Flemish inheritance rules, kot budgets, student jobs). Good moments, but it is a variant of A.

---

## Scoring matrix (my estimate, 1–5)

| Criterion (weight) | A. Foresight | B. Autopilot | C. Immune System | D. Personal Economist |
|---|---|---|---|---|
| Originality (30%) | 4: forward-looking calendar is fresh, though "life events" exist | 5: natural-language mandates across bank+insurance | 4: protect-not-sell and care mode is a rare framing | 5: personalizing on the world instead of the person; nobody does it |
| Technical ability tonight (30%) | 5: deterministic rules, easy end to end | 3: compiler + simulator + limits must all work | 4: detectors and tiers are simple | 4: deterministic, but rules must be encoded correctly |
| Fit to the case (30%) | 5: all five questions, "right moment" is the core | 4: strong on adapt / cross-product / scale, weaker on signals | 4: strong on signals and support, weaker on guiding | 5: question 5 ("millions at the same time") answered literally; cross-product by construction |
| Security (10%) | 4: standard auth/IDOR story | 5: business-logic limits showcase | 4: standard, plus hold logic | 4: standard |
| Demo wow in 3 minutes | 4 | 5 (voice → mandate → money moves → Kate asks) | 4 (the 22:40 fraud call) | 5 (headline → rule → 2.3M personal impacts in seconds) |
| Risk the jury says "this exists" | Medium (Kate nudges, Personetics) | Medium (rules, standing orders) | Medium (fraud engine) | Low |
| Build risk with 4 people in 3.5 h | Low | High | Medium | Low–medium |

**My ranking for tonight:** D and A are co-leaders. D is more original and has the better 3-minute demo; A is the most literal answer to "right moment". C is the most defensible ethically and lands hardest with a KBC jury that lives "role in society". B is the biggest idea and the most on-trend, but a mandate demo that half-works reads as unsafe. **For the final on 20 Oct:** B, then D, then A, then C.

**The natural merge:** A and D are the same engine with two calendars, yours and the world's. If the team is split between them, build D's rulebook as one more trigger source inside A's moment engine and pitch "Kate Foresight: two calendars". That costs almost nothing extra because they share the dataset, the arbitration, the narration and the control room.

**Other combinations:** A + B (moments become one-tap mandates), A + C (care mode inside the moments engine), B + C (a guardian mandate is an immune response). Whatever you pick tonight, say in the video which of the others is the next layer.

---

## How to decide in 10 minutes

1. Each person reads the four one-liners and the matrix (3 min).
2. Each person scores A, B, C, D from 1–5 on two questions only: "Can we demo this working by 21:45?" and "Would a KBC jury remember it tomorrow?" (2 min).
3. Add up. If two are tied, take the one with the lower build risk. Decide, write the name on the whiteboard, do not revisit (5 min).
4. Whoever argued hardest for a losing idea writes the "next layer" line for the video.
