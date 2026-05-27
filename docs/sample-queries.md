# Sample TAM Queries

A test set of realistic market-sizing questions, phrased the way a VC actually
types them, for exercising Strata's framework-selection and source-attribution
end-to-end. Every query is anchored to a real company from a live diligence
pipeline, so the markets are concrete rather than hypothetical.

## How to read this

- Each query is a question you'd type into the pyramid graph.
- The *italic tag* after each notes the **sizing angle** it should trigger —
  use it to check the engine picks the right framework family.
- Queries are grouped by the company whose market they cover. Every company has
  ≥1 query; higher-priority / multi-angle markets have more.

Framework families stressed across the set: **bottoms-up by seat**, **top-down
from spend**, **analog / penetration**, **comparable-market / share-shift**,
**labor displacement**, plus non-seat units (**capacity/MW**, **GMV / take-rate**,
**usage-based**, **services revenue**) and one deliberately **forward-looking**
case (#29) to test where the engine refuses (per the no-forecasting non-goal in
[`05-roadmap.md`](05-roadmap.md)).

## Coverage map

| # range | Company | Website | Market the query must cover |
|---|---|---|---|
| 1–4   | Kyber        | askkyber.com    | AI doc-gen + workflow automation for P&C insurers ($150K ACV) |
| 5–8   | Gather       | gatherhq.com    | AI customer-/market-research automation for marketing teams |
| 9–12  | Echelon      | echelonai.com   | AI agents automating ServiceNow platform dev/maintenance |
| 13–16 | Endeavor     | endeavor.ai     | AI back-office automation (quote/order/finance) for mfg & distribution |
| 17–20 | Skyramp      | skyramp.dev     | AI software test generation & QA automation |
| 21–23 | Supermemory  | supermemory.ai  | Memory / context infrastructure for AI agents |
| 24–26 | Numeral      | numeral.com     | Sales-tax / VAT compliance automation for ecommerce & SaaS |
| 27–29 | Yotta        | yotta.com       | India sovereign cloud / hyperscale data center / AI compute |
| 30–32 | SignalLabs   | (Ronanki)       | Enterprise AI decision/attention + institutional-memory layer (healthcare-led) |
| 33–35 | Zero RFI     | zero-rfi.com    | AI-native construction management / owner's-rep roll-up |
| 36–38 | Contrario AI | contrario.ai    | AI recruiting (vertical agents + recruiter marketplace, Slack/ATS-native) |
| 39–41 | MetaVoice    | metavoice.io    | Voice AI infrastructure (open TTS / conversational speech foundation models) |
| 42–44 | Miravoice    | miravoice.com   | AI voice agents for quantitative phone surveys & market research |
| 45–47 | PlayerZero   | playerzero.ai   | AI code quality / production engineering (predictive debug + code simulation) |
| 48–50 | Kaizen Labs  | kaizenlabs.co   | GovTech — resident-services / commerce platform for state & local |
| 51–53 | Sieve        | sieve.ai        | Video/audio AI infrastructure (multimodal data lab — media APIs + dataset tooling) |
| 54–56 | Piramidal    | piramidal.ai    | AI neurodiagnostics — foundation model for EEG/brainwaves |
| 57–59 | ST Labs      | stlabs.com      | AI-native ITSM — agent-orchestrated service mgmt + CMDB ("Axiom") |
| 60–62 | Wraithwatch  | wraithwatch.com | Agentic cyber defense (autonomous attack-path modeling + mitigation) |
| 63–65 | Moda         | moda.app        | AI design — brand-aligned creative agent (decks, social, reports) |
| 66–68 | Minerva      | tryminerva.ai   | AI-native accounting firm — bookkeeping/tax for SMBs (services) |
| 69–71 | Effective AI | effectiveai.com | AI agents for insurance knowledge work — actuarial, product, underwriting |
| 72–74 | Melius       | trymelius.com   | AI creative canvas — multi-model image/video generation for marketing/creators |
| 75–77 | Accrual      | accrual.com     | AI-native tax & accounting automation software for CPA firms |

---

## The queries

### Kyber — AI doc-gen / workflow automation for P&C insurers
1. "How big is the market for AI document-generation and workflow-automation software sold to US P&C insurance carriers?" *(bottoms-up by carrier × seat × ACV; top-down from P&C IT/ops spend)*
2. "What's the TAM if every US P&C carrier above $100M in written premium adopts a doc-gen/workflow co-pilot at ~$150K ACV?" *(bottoms-up anchored on Kyber's actual ACV — direct regression case)*
3. "How much of P&C insurers' back-office labor spend — underwriting ops, policy issuance, claims docs — is addressable by automation?" *(labor displacement, top-down)*
4. "What's the analog TAM for P&C workflow automation if it penetrates like claims-management SaaS did over the last decade?" *(analog/penetration)*

### Gather — AI customer-research automation for marketing
5. "How big is the market for AI-driven customer/market-research automation sold to B2B and B2C marketing teams in North America?" *(bottoms-up by # marketing orgs × research budget)*
6. "What share of qualitative-research and insights spend — surveys, focus groups, expert calls — is displaceable by AI automation?" *(displacement of the legacy insights industry)*
7. "What's the TAM for continuous voice-of-customer tooling priced per marketing seat across US enterprises?" *(bottoms-up by seat)*
8. "How big is the expert-network / primary-research market (GLG, Tegus-style) that AI research tools could partially substitute?" *(comparable-market substitution)*

### Echelon — AI agents for ServiceNow platform dev
9. "How big is the market for AI agents that automate ServiceNow platform development and maintenance for enterprises?" *(bottoms-up by # ServiceNow customers × implementation spend)*
10. "What's the TAM if AI automates a meaningful share of the ServiceNow systems-integrator / professional-services market?" *(SI/PS labor displacement)*
11. "How big is the broader market for AI agents that configure and maintain enterprise SaaS platforms (ServiceNow + Salesforce + SAP)?" *(adjacent-expansion / platform-ecosystem TAM)*
12. "What's addressable from enterprise ServiceNow developer/admin headcount cost if agents do the work?" *(labor displacement, by seat)*

### Endeavor — AI back-office automation for mfg & distribution
13. "How big is the market for AI workflow automation (quoting, order entry, financial ops) sold to US manufacturers and distributors?" *(bottoms-up by # firms × ACV)*
14. "What's the TAM for AI agents automating quote-to-cash for mid-to-large industrial distributors globally?" *(top-down from quote-to-cash labor / ERP-adjacent spend)*
15. "How much of manufacturing & distribution back-office labor cost is addressable by process-automation AI?" *(labor displacement, BLS-anchored)*
16. "What's the analog TAM for industrial back-office AI if it penetrates like ERP/MES did across discrete + process manufacturing?" *(analog/penetration)*

### Skyramp — AI software testing / QA automation
17. "How big is the market for AI-powered software test generation and QA automation, globally?" *(bottoms-up by # developers/QA engineers × tool spend)*
18. "What's the TAM if AI testing tools displace a share of the manual QA / SDET labor market?" *(labor displacement)*
19. "How big is the automated-testing software market — API, E2E, integration — that an AI-native entrant could take?" *(comparable-market vs. incumbents)*
20. "What's the addressable testing/QA tooling spend per engineering org across the SaaS company universe?" *(bottoms-up by company × eng-team size)*

### Supermemory — AI memory / context infrastructure
21. "How big is the market for AI memory / context-management infrastructure sold to developers and enterprises building agents?" *(bottoms-up by # AI-app developers × infra spend)*
22. "What's the TAM for the 'memory layer' as a share of the AI application infra / vector-DB + retrieval market?" *(share-of-AI-infra-stack)*
23. "What's the usage-based revenue if memory APIs attach to LLM-app builds the way databases attach to web apps?" *(attach-rate analog)*

### Numeral — sales-tax / VAT compliance automation
24. "How big is the market for automated US sales-tax and global VAT compliance software for ecommerce and SaaS businesses?" *(bottoms-up by # sellers/SaaS cos × ACV)*
25. "What's the TAM if sales-tax automation penetrates the long tail of SMB ecommerce sellers below the Avalara/Vertex enterprise tier?" *(underserved-SMB bottoms-up)*
26. "How big is the transaction-tax compliance market an automation-first entrant could take from Avalara and Vertex?" *(comparable-market / share-shift)*

### Yotta — India sovereign cloud / data center / AI compute
27. "How big is the data-center colocation and hyperscale capacity market in India?" *(capacity-based: India DC MW × revenue/MW — non-seat unit)*
28. "What's the TAM for sovereign / India-hosted cloud services for regulated enterprises and government?" *(top-down from India cloud spend × sovereign-eligible share)*
29. "How big is the India GPU-as-a-service / AI-compute market over the next 5 years?" *(GPU capacity × utilization × price — forward-looking; deliberately bumps the no-forecasting non-goal)*

### SignalLabs — enterprise AI decision/attention layer (healthcare-led)
30. "How big is the market for an enterprise AI decision/attention orchestration layer sold to healthcare payers and providers?" *(bottoms-up by # payers/health systems × ACV — lead vertical)*
31. "What's the cross-industry TAM for institutional-knowledge / decision-intelligence AI across healthcare, financial services, logistics, and infrastructure?" *(sum-of-verticals)*
32. "How much enterprise spend on BI + knowledge management + workflow tooling is addressable by an AI decision layer?" *(displacement of adjacent budgets)*

### Zero RFI — AI-native construction management / owner's rep
33. "How big is the US owner's-representative and construction-management services market that an AI-native firm could roll up?" *(services revenue: project value × owner's-rep fee %)*
34. "What's the TAM for AI that reduces RFIs, change orders, and rework across US commercial construction?" *(top-down from construction spend × rework/RFI cost %)*
35. "How big is the construction-tech software market for building owners and developers specifically (vs. GCs and trades)?" *(underserved-buyer segment sizing)*

### Contrario AI — AI recruiting (vertical agents + recruiter marketplace)
36. "How big is the market for AI recruiting agents sold to in-house talent-acquisition teams in North America?" *(bottoms-up by # recruiters/TA orgs × seat/ACV)*
37. "What share of staffing-agency and contingent-recruiting spend is displaceable by AI sourcing/screening agents?" *(displacement of the staffing/recruiting-agency market)*
38. "What's the GMV / take-rate TAM for a recruiter marketplace matching candidates to roles?" *(marketplace take-rate on placements)*

### MetaVoice — voice AI infrastructure (TTS / speech foundation models)
39. "How big is the market for text-to-speech and conversational speech APIs sold to developers building voice apps?" *(bottoms-up by # voice-app developers × usage)*
40. "What's the TAM for speech/voice foundation-model infrastructure as a share of the broader generative-AI API market?" *(share-of-AI-infra)*
41. "What's the addressable voice-API spend if TTS attaches to the conversational-AI / voice-agent application market?" *(attach-rate to voice agents)*

### Miravoice — AI voice agents for phone surveys & market research
42. "How big is the phone-based quantitative market-research (CATI) market that AI voice agents could automate?" *(displacement of CATI / phone-survey research spend)*
43. "What's the TAM for AI voice agents conducting surveys, priced per completed interview, across US research buyers?" *(bottoms-up by # interviews × per-complete cost)*
44. "How much market-research call-center / field-interview labor is addressable by automated voice agents?" *(labor displacement)*

### PlayerZero — AI code quality / production engineering
45. "How big is the market for AI code-quality and production-debugging tools sold to software engineering teams?" *(bottoms-up by # eng orgs × tool spend)*
46. "What share of observability / APM and error-monitoring spend could a predictive code-quality tool capture?" *(comparable-market / share of observability spend)*
47. "How much engineering time on debugging and incident resolution is addressable by AI?" *(labor displacement, by developer-hour)*

### Kaizen Labs — GovTech resident-services / commerce for state & local
48. "How big is the market for resident-services and citizen-engagement software sold to US state and local agencies?" *(top-down from state/local govtech IT spend)*
49. "What's the TAM for a modern resident-services platform priced per agency/municipality across the US?" *(bottoms-up by # municipalities/agencies × ACV)*
50. "What's the payments TAM from resident transactions — permits, utilities, fees — at a take-rate?" *(payments GMV × take-rate)*

### Sieve — video/audio AI infrastructure (multimodal data lab)
51. "How big is the market for video/audio AI processing APIs sold to developers and media teams?" *(bottoms-up by # multimodal developers × usage)*
52. "What's the TAM for multimodal media infrastructure as a share of the AI application infra stack?" *(share-of-AI-infra)*
53. "How big is the dataset-curation / data-tooling market for training multimodal (video/audio) models?" *(comparable / data-infra sizing)*

### Piramidal — AI neurodiagnostics (EEG foundation model)
54. "How big is the clinical EEG / neurodiagnostics market that an AI foundation model could augment in the US?" *(top-down from EEG procedure volume × reimbursement/price)*
55. "What's the TAM for AI-assisted EEG interpretation sold to hospitals and neurology departments?" *(bottoms-up by # neurology depts/hospitals × ACV)*
56. "How much neurologist / EEG-technician interpretation labor is addressable by an AI brainwave model?" *(labor augmentation/displacement)*

### ST Labs — AI-native ITSM + CMDB ("Axiom")
57. "How big is the IT service management (ITSM) software market that an AI-native platform could take from incumbents like ServiceNow?" *(comparable-market / share-shift)*
58. "What's the TAM for AI-native ITSM + CMDB priced per IT seat across mid-to-large enterprises?" *(bottoms-up by # IT orgs × seat)*
59. "How much combined ITSM + ITOM + IT-ops labor spend is addressable by agent-orchestrated service management?" *(displacement of adjacent IT budgets + labor)*

### Wraithwatch — agentic cyber defense
60. "How big is the market for agentic / autonomous cyber-defense software sold to F500 enterprises and government?" *(bottoms-up by # large orgs/agencies × security ACV)*
61. "What share of security-operations (SOC, threat detection, vuln management) spend could autonomous defense capture?" *(share of SecOps spend)*
62. "How much red-team / penetration-testing and SOC-analyst labor is addressable by autonomous attack-path AI?" *(labor displacement)*

### Moda — AI brand-aligned creative agent
63. "How big is the market for AI brand-design agents that produce presentations, social, and reports for marketing teams?" *(bottoms-up by # marketing/brand teams × seat)*
64. "What share of design-tool and creative-agency spend (Canva/Adobe + agencies) is addressable by an AI design agent?" *(displacement of design tools + agency spend)*
65. "What's the per-seat TAM across knowledge workers who build decks and branded content?" *(bottoms-up by knowledge-worker seat)*

### Minerva — AI-native accounting firm for SMBs (services)
66. "How big is the SMB bookkeeping, accounting, and tax-prep services market in the US that an AI-native firm could serve?" *(services TAM: # SMBs × annual accounting spend)*
67. "What's the TAM if AI-native accounting captures the SMB segment underserved by traditional CPA firms?" *(underserved-segment bottoms-up)*
68. "How much SMB accounting/bookkeeping labor cost is displaceable by end-to-end AI delivery?" *(labor displacement)*

### Effective AI — AI agents for insurance knowledge work
69. "How big is the market for AI agents automating actuarial, product, and underwriting knowledge work at insurers?" *(bottoms-up by # insurers × actuarial/underwriting headcount × ACV)*
70. "How much insurance actuarial and underwriting labor spend is addressable by AI knowledge agents?" *(labor displacement, top-down)*
71. "What's the analog TAM for insurance knowledge-work AI if it penetrates like core policy-admin systems did?" *(analog/penetration — same industry as Kyber, different function)*

### Melius — AI creative canvas (multi-model image/video)
72. "How big is the market for AI image and video generation tools sold to marketers and creators?" *(bottoms-up by # creators/marketers × subscription)*
73. "What share of creative-production, stock-media, and video-agency spend is displaceable by multi-model generative tools?" *(displacement of creative production + stock + agency)*
74. "What's the TAM for a multi-model creative canvas priced per seat across content/creative teams?" *(bottoms-up by seat)*

### Accrual — AI tax & accounting automation for CPA firms
75. "How big is the market for AI tax-and-accounting automation software sold to CPA and accounting firms?" *(bottoms-up by # CPA firms × seat/ACV)*
76. "What share of professional tax-prep software spend (Intuit, Thomson Reuters, Wolters Kluwer) could an AI-native entrant take?" *(comparable-market / share-shift)*
77. "How much CPA-firm preparer labor on federal and state form preparation is addressable by automation?" *(labor displacement)*

---

## Disambiguation test cases (a feature, not a bug)

Several companies sit in adjacent markets on purpose — these pairs stress whether
the engine returns **distinct** TAMs for neighboring segments instead of reciting
the same parent market:

- **Echelon (9–12)** *automates* ServiceNow vs. **ST Labs (57–59)** *replaces* it
  with an AI-native ITSM platform — same ITSM market, opposite wedge.
- **Kyber (1–4)** P&C doc-gen vs. **Effective AI (69–71)** insurance actuarial/
  underwriting — same industry, different function.
- **Gather (5–8)** customer-research automation vs. **Miravoice (42–44)** AI phone-
  survey agents — both disrupt market research, different modality.
- **MetaVoice (39–41)** speech infra vs. **Miravoice (42–44)** voice-survey app vs.
  **Sieve (51–53)** video/audio infra — infra-vs-application across the voice/
  multimodal stack.
- **Moda (63–65)** brand-design agent vs. **Melius (72–74)** multi-model image/
  video gen — both AI creative, different output.
- **Minerva (66–68)** AI accounting *firm* (services) vs. **Accrual (75–77)** AI
  accounting *software* for CPA firms — same industry, services vs. tooling.

A correct answer should size each of these *narrowly* and trace the difference to
its source primitives — not collapse them into one number.
