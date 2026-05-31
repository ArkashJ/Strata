// Wave 5C — /integrations gallery (AC5C.2/3/4). Server Component reading a static
// catalog: three groups of cards, the old-vs-new comparison, and the animated
// pipeline flow.
import type { Metadata } from "next";

import { IntegrationCard } from "./IntegrationCard";
import { OldVsNewCard } from "./OldVsNewCard";
import { PipelineFlow } from "./PipelineFlow";
import { GROUP_LABEL, type IntegrationGroup, byGroup } from "./integrations";

export const metadata: Metadata = {
  title: "Integrations · Strata",
  description: "Connect your SaaS data, push Strata numbers, and the public data bank.",
};

const GROUPS: IntegrationGroup[] = ["inbound", "outbound", "public"];

export default function IntegrationsPage() {
  return (
    <main className="mx-auto flex w-full max-w-[var(--content-max)] flex-1 flex-col gap-10 px-8 py-8">
      <header className="flex flex-col gap-2">
        <h1 className="display text-[34px] leading-[1.05] text-[var(--fg-1)]">Integrations</h1>
        <p className="max-w-[640px] text-[14px] text-[var(--fg-3)]">
          Strata runs on sourced numbers — government data, the web, and{" "}
          <span className="text-[var(--fg-1)]">your own connected SaaS</span>, which becomes private
          first-party data that sharpens only your TAMs.
        </p>
      </header>

      <section className="flex flex-col gap-3">
        <h2 className="text-[13px] uppercase tracking-[0.06em] text-[var(--fg-3)]">How it works</h2>
        <PipelineFlow />
      </section>

      <OldVsNewCard />

      {GROUPS.map((group) => (
        <section key={group} className="flex flex-col gap-3">
          <h2 className="display text-[20px] text-[var(--fg-1)]">{GROUP_LABEL[group]}</h2>
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {byGroup(group).map((integration) => (
              <IntegrationCard key={integration.provider} integration={integration} />
            ))}
          </div>
        </section>
      ))}
    </main>
  );
}
