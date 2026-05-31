import type { Metadata } from "next";

// Client-facing platform walkthrough. Screenshot-driven, business-language —
// the deliverable a partner reads before their first session. Screenshots live
// in /public/guides and are captured from the live app (see the repo handbook
// docs/guides/CLIENT_PLATFORM_GUIDE.md for the regeneration recipe).

export const metadata: Metadata = {
  title: "Guides — Strata",
  description: "A walkthrough of Strata: defensible, reproducible TAM you can put in a memo.",
};

interface Section {
  id: string;
  kicker: string;
  title: string;
  body: string[];
  image?: string;
  caption?: string;
}

const VALUE_ROWS: [string, string, string][] = [
  ["Numbers", "Plausible prose, often unsourced", "Every input is a sourced primitive: URL + tier + sha256 snapshot"],
  ["Reproducible", "Re-run → a different answer", "Hash-pinned /tam/<id> — frozen, citable, shareable forever"],
  ["The math", 'Black-box "≈ $X B"', "Explicit equation: workforce × spend = TAM, every factor clickable"],
  ["Defensible", "Can't defend to an IC/LP", "Triangulation across ≥2 method families + independence score"],
  ["Your data", "Can't ingest", "OAuth CRM connectors → org-scoped private primitives feed your TAM"],
  ["Honesty", "Hides modeled assumptions", "Loud banner when any input is modeled vs externally sourced"],
];

const SECTIONS: Section[] = [
  {
    id: "home",
    kicker: "01 · First impression",
    title: "Describe a market in plain language",
    body: [
      "Strata turns a one-line market description into a defensible TAM. Type a market — “AI coding assistants for software developers, US” — and Strata picks the framework, pre-fills the sourced primitives, and returns a range you can cite.",
      "The left rail is your library: live counts of every Concept, Primitive, and Framework in the data bank. Nothing here is invented — each number traces to a source.",
    ],
    image: "/guides/01-home.png",
    caption: "The Strata home page: a single query box over a live, sourced data bank.",
  },
  {
    id: "build",
    kicker: "02 · Build your own TAM",
    title: "See the math, not a black box",
    body: [
      "Strata resolves your query into a scenario tree and shows exactly how the number is built: the bar chart of inputs, and the explicit equation — “Multiplies to 3M people × $300/seat-year = $900M”. This is the receipt an LLM chat can’t produce.",
      "Each input carries its source tier. When a figure is community-modeled rather than externally sourced, a banner says so plainly — so the headline number is never mistaken for a regulator citation.",
    ],
    image: "/guides/02-build-result.png",
    caption: "A resolved TAM with the explicit equation, per-input source tiers, and an honesty banner.",
  },
  {
    id: "primitive",
    kicker: "03 · Every number is sourced",
    title: "Click any input down to its citation",
    body: [
      "Every primitive has its own page: the value, the structured unit, the methodology, and a Source Snapshot — the source URL, its tier (regulator, aggregator, analyst, community-modeled…), and the content hash that pins it. Two analysts re-running the same TAM get the same number.",
    ],
    image: "/guides/03-primitive-detail.png",
    caption: "A primitive detail page: value, unit, methodology, and a hash-pinned source snapshot.",
  },
  {
    id: "concept",
    kicker: "04 · Competing measurements",
    title: "Disagreement gets a page, not a footnote",
    body: [
      "Real markets have competing measurements. Strata treats a concept as first-class: multiple sourced estimates attach to one concept, and the disagreement between them is shown — so you can see the spread and choose, instead of trusting one opaque figure.",
    ],
    image: "/guides/04-concept-detail.png",
    caption: "A concept page showing competing, independently-sourced measurements.",
  },
  {
    id: "pyramid",
    kicker: "05 · Explore the pyramid",
    title: "Navigate by qualitative, quantitative, and industry",
    body: [
      "The pyramid graph is the map of the data bank. Filter by geography, time, and market stage; click a node to narrow the view and see which frameworks can size it. It’s how you discover what’s already been measured before you build.",
    ],
    image: "/guides/05-pyramid-graph.png",
    caption: "The pyramid explorer: three analysis axes with geo / time / stage filters.",
  },
  {
    id: "artifact",
    kicker: "06 · The shareable artifact",
    title: "A permalink you paste into a memo",
    body: [
      "Every TAM gets a permanent, content-addressed URL (/tam/<hash>) that resolves forever — copy it into a partner memo and it stays exactly as you left it. The artifact shows the headline range, the scenario tree, a Source Tier Mix (how many inputs are regulator vs modeled), a sensitivity tornado (which assumption moves the answer most), and one-click Markdown / PDF export.",
    ],
    image: "/guides/06-tam-artifact.png",
    caption: "A frozen TAM artifact: permalink, method families, source-tier mix, and export.",
  },
  {
    id: "dashboard",
    kicker: "07 · Your workspace",
    title: "Sign in and keep your work",
    body: [
      "A simple sign-in attributes your saved TAMs and activity. The dashboard is your home base — saved builds, recent activity, and an audit trail of every resolve and recompute.",
    ],
    image: "/guides/07-dashboard.png",
    caption: "The dashboard: your saved TAMs and activity trail after signing in.",
  },
  {
    id: "integrations",
    kicker: "08 · Connect your data",
    title: "Feed your own CRM into the model",
    body: [
      "Connect a SaaS source (e.g. HubSpot) and Strata turns it into private, org-scoped first-party primitives — isolated to your tenant, encrypted at rest, and fed into the same evaluator with a private banner. Your proprietary numbers, the same defensible math.",
    ],
    image: "/guides/08-integrations.png",
    caption: "The integrations gallery: connect a CRM to generate private first-party primitives.",
  },
  {
    id: "browse",
    kicker: "09 · Browse promoted TAMs",
    title: "Start from work that's already done",
    body: [
      "The browse registry lists promoted, public TAMs — a starting library of defensible market sizes you can fork and adapt to your thesis.",
    ],
    image: "/guides/09-browse.png",
    caption: "The public registry of promoted TAMs.",
  },
];

function ValueProp() {
  return (
    <div className="canvas-card overflow-hidden" style={{ borderRadius: "var(--r-3)" }}>
      <table className="w-full text-left text-[13px]">
        <thead>
          <tr className="border-b border-[var(--border-1)] text-[11px] uppercase tracking-[0.04em] text-[var(--fg-3)]">
            <th className="px-4 py-3 font-medium" />
            <th className="px-4 py-3 font-medium">5 minutes of an LLM chat</th>
            <th className="px-4 py-3 font-medium text-[var(--accent)]">Strata</th>
          </tr>
        </thead>
        <tbody>
          {VALUE_ROWS.map(([dim, llm, strata]) => (
            <tr key={dim} className="border-b border-[var(--border-1)] last:border-0 align-top">
              <td className="px-4 py-3 font-medium text-[var(--fg-1)]">{dim}</td>
              <td className="px-4 py-3 text-[var(--fg-3)]">{llm}</td>
              <td className="px-4 py-3 text-[var(--fg-2)]">{strata}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export default function GuidesPage() {
  return (
    <main className="mx-auto w-full max-w-[var(--content-max)] px-6 py-10">
      <header className="max-w-[680px]">
        <div className="text-[11px] uppercase tracking-[0.06em] text-[var(--fg-3)]">
          Platform guide
        </div>
        <h1 className="display mt-2 text-[40px] leading-[1.05] text-[var(--fg-1)]">
          A defensible TAM you can put in a memo.
        </h1>
        <p className="mt-4 text-[15px] leading-relaxed text-[var(--fg-2)]">
          Strata replaces a $30k analyst report — and beats five minutes of an LLM chat — with
          sourced, reproducible, customizable market sizing. This walkthrough shows the whole
          surface, page by page.
        </p>
      </header>

      <section className="mt-8">
        <h2 className="text-[13px] uppercase tracking-[0.04em] text-[var(--fg-3)]">
          Why this beats an LLM answer
        </h2>
        <div className="mt-3">
          <ValueProp />
        </div>
      </section>

      <nav className="mt-10 flex flex-wrap gap-2" aria-label="Guide contents">
        {SECTIONS.map((s) => (
          <a
            key={s.id}
            href={`#${s.id}`}
            className="rounded-[var(--r-2)] border border-[var(--border-1)] px-3 py-1.5 text-[12px] text-[var(--fg-2)] transition-colors hover:border-[var(--border-3)] hover:text-[var(--fg-1)]"
          >
            {s.kicker.split(" · ")[1] ?? s.kicker}
          </a>
        ))}
      </nav>

      <div className="mt-12 flex flex-col gap-16">
        {SECTIONS.map((s) => (
          <section key={s.id} id={s.id} className="scroll-mt-24">
            <div className="text-[11px] uppercase tracking-[0.06em] text-[var(--accent)]">
              {s.kicker}
            </div>
            <h2 className="mt-2 text-[24px] font-medium text-[var(--fg-1)]">{s.title}</h2>
            <div className="mt-3 flex max-w-[680px] flex-col gap-3 text-[14px] leading-relaxed text-[var(--fg-2)]">
              {s.body.map((p) => (
                <p key={p.slice(0, 24)}>{p}</p>
              ))}
            </div>
            {s.image ? (
              <figure className="mt-5">
                {/* Static walkthrough captures — plain img keeps them outside Next's optimizer. */}
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img
                  src={s.image}
                  alt={s.caption ?? s.title}
                  className="w-full rounded-[var(--r-3)] border border-[var(--border-1)]"
                />
                {s.caption ? (
                  <figcaption className="mt-2 text-[12px] text-[var(--fg-3)]">
                    {s.caption}
                  </figcaption>
                ) : null}
              </figure>
            ) : null}
          </section>
        ))}
      </div>

      <section className="mt-16 border-t border-[var(--border-1)] pt-8">
        <h2 className="text-[20px] font-medium text-[var(--fg-1)]">Live today vs. coming soon</h2>
        <div className="mt-4 grid gap-6 sm:grid-cols-2">
          <div>
            <div className="text-[12px] font-medium uppercase tracking-[0.04em] text-[var(--tier-regulator)]">
              Live
            </div>
            <ul className="mt-2 flex flex-col gap-1.5 text-[13px] text-[var(--fg-2)]">
              <li>Free-form query → sourced TAM with the explicit equation</li>
              <li>Hash-pinned, shareable /tam/&lt;id&gt; artifact (survives restarts)</li>
              <li>Per-input source-tier mix + sensitivity tornado + Markdown/PDF export</li>
              <li>Simple sign-in; pyramid explorer; concept disagreement view</li>
            </ul>
          </div>
          <div>
            <div className="text-[12px] font-medium uppercase tracking-[0.04em] text-[var(--fg-3)]">
              Coming soon
            </div>
            <ul className="mt-2 flex flex-col gap-1.5 text-[13px] text-[var(--fg-3)]">
              <li>Live CRM (HubSpot) sync — gallery is wired, OAuth pilot in progress</li>
              <li>Triangulated hero concepts with competing measurements</li>
              <li>Deeper verticals (e.g. semiconductor value chain) </li>
              <li>Metered micropayments &amp; team workspaces</li>
            </ul>
          </div>
        </div>
      </section>

      <p className="mt-12 text-[11px] text-[var(--fg-4)]">
        Screenshots captured from the live app, 2026-05-30. Regeneration recipe:
        docs/guides/CLIENT_PLATFORM_GUIDE.md.
      </p>
    </main>
  );
}
