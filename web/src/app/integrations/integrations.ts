// Wave 5C — the /integrations catalog. Three groups: Inbound (connect your SaaS
// → private primitives), Outbound (where Strata pushes numbers), and the Public
// data bank (the 15 gov/aggregator connectors that feed every public TAM).
export type IntegrationStatus = "connected" | "available" | "coming-soon";
export type IntegrationGroup = "inbound" | "outbound" | "public";

export interface Integration {
  provider: string;
  name: string;
  group: IntegrationGroup;
  status: IntegrationStatus;
  blurb: string;
}

export const INTEGRATIONS: Integration[] = [
  // Inbound — connect-your-data (Wave 5B). HubSpot/Stripe are the pilots.
  {
    provider: "hubspot",
    name: "HubSpot",
    group: "inbound",
    status: "available",
    blurb: "CRM companies & pipeline → private first-party primitives.",
  },
  {
    provider: "stripe",
    name: "Stripe",
    group: "inbound",
    status: "coming-soon",
    blurb: "Billing & ARR → private revenue primitives.",
  },
  {
    provider: "salesforce",
    name: "Salesforce",
    group: "inbound",
    status: "coming-soon",
    blurb: "Accounts & opportunities.",
  },
  {
    provider: "snowflake",
    name: "Snowflake",
    group: "inbound",
    status: "coming-soon",
    blurb: "Warehouse tables as primitives.",
  },
  {
    provider: "airtable",
    name: "Airtable",
    group: "inbound",
    status: "coming-soon",
    blurb: "Operational bases.",
  },
  {
    provider: "quickbooks",
    name: "QuickBooks",
    group: "inbound",
    status: "coming-soon",
    blurb: "Financials & revenue.",
  },

  // Outbound — where Strata's sourced numbers go.
  {
    provider: "anthropic",
    name: "Claude (MCP)",
    group: "outbound",
    status: "connected",
    blurb: "Strata MCP server — sourced, hash-pinned TAMs in your agent.",
  },
  {
    provider: "google sheets",
    name: "Google Sheets",
    group: "outbound",
    status: "coming-soon",
    blurb: "Export a TAM to a live sheet.",
  },
  {
    provider: "slack",
    name: "Slack",
    group: "outbound",
    status: "coming-soon",
    blurb: "Share a TAM card to a channel.",
  },
  {
    provider: "notion",
    name: "Notion",
    group: "outbound",
    status: "coming-soon",
    blurb: "Embed a TAM in a doc.",
  },

  // Public data bank — the 15 gov/aggregator connectors.
  {
    provider: "bls",
    name: "BLS",
    group: "public",
    status: "connected",
    blurb: "Employment, wages, CPI, JOLTS.",
  },
  {
    provider: "fred",
    name: "FRED",
    group: "public",
    status: "connected",
    blurb: "GDP, rates, money supply.",
  },
  {
    provider: "census",
    name: "Census",
    group: "public",
    status: "connected",
    blurb: "Industry stats by NAICS.",
  },
  {
    provider: "edgar",
    name: "EDGAR",
    group: "public",
    status: "connected",
    blurb: "Company financials (XBRL).",
  },
  {
    provider: "world bank",
    name: "World Bank",
    group: "public",
    status: "connected",
    blurb: "Global GDP, population.",
  },
  {
    provider: "oecd",
    name: "OECD",
    group: "public",
    status: "connected",
    blurb: "38-country macro.",
  },
  {
    provider: "eurostat",
    name: "Eurostat",
    group: "public",
    status: "connected",
    blurb: "EU sector stats.",
  },
  {
    provider: "comtrade",
    name: "UN Comtrade",
    group: "public",
    status: "connected",
    blurb: "Bilateral trade flows.",
  },
  {
    provider: "fdic",
    name: "FDIC",
    group: "public",
    status: "connected",
    blurb: "Bank financials.",
  },
  {
    provider: "cms",
    name: "CMS",
    group: "public",
    status: "connected",
    blurb: "Medicare/Medicaid.",
  },
  { provider: "eia", name: "EIA", group: "public", status: "connected", blurb: "Energy." },
  {
    provider: "usda nass",
    name: "USDA NASS",
    group: "public",
    status: "connected",
    blurb: "Crops & livestock.",
  },
  { provider: "faa", name: "FAA", group: "public", status: "connected", blurb: "Aviation." },
  {
    provider: "openfda",
    name: "openFDA",
    group: "public",
    status: "connected",
    blurb: "Drugs & devices.",
  },
  {
    provider: "kalshi",
    name: "Kalshi",
    group: "public",
    status: "connected",
    blurb: "Prediction-market signals (non-sizing).",
  },
];

export const GROUP_LABEL: Record<IntegrationGroup, string> = {
  inbound: "Inbound — connect your data",
  outbound: "Outbound — push Strata numbers",
  public: "Public data bank",
};

export function byGroup(group: IntegrationGroup): Integration[] {
  return INTEGRATIONS.filter((i) => i.group === group);
}
