// Wave 5C / AC5C.1 — name → brand SVG mark, backed by simple-icons. Unknown
// names resolve to `null` so <BrandIcon> can render a safe fallback glyph and
// never crash. Gov/source marks (not in simple-icons) use a hand hex + the
// monogram fallback.
// Individual (tree-shakeable) imports — only the marks we render ship in the
// bundle, and it stays small even if BrandIcon ever becomes a client component.
// Vendors dropped from simple-icons v16 (Slack/Salesforce/Segment) are
// intentionally absent → they fall back to a monogram.
import {
  type SimpleIcon,
  siAirtable,
  siAnthropic,
  siClaude,
  siGithub,
  siGmail,
  siGooglesheets,
  siHubspot,
  siJira,
  siLinear,
  siNotion,
  siQuickbooks,
  siSnowflake,
  siStripe,
} from "simple-icons";

export interface BrandMark {
  path: string;
  hex: string;
  title: string;
}

// Vendor name (lowercased) → simple-icons mark.
const MARKS: Record<string, SimpleIcon> = {
  github: siGithub,
  gmail: siGmail,
  notion: siNotion,
  jira: siJira,
  linear: siLinear,
  hubspot: siHubspot,
  snowflake: siSnowflake,
  stripe: siStripe,
  quickbooks: siQuickbooks,
  "google sheets": siGooglesheets,
  googlesheets: siGooglesheets,
  airtable: siAirtable,
  anthropic: siAnthropic,
  claude: siClaude,
};

// Gov / public-data source marks aren't in simple-icons — give them a tinted
// monogram (the BrandIcon fallback renders the first letters).
const GOV_HEX: Record<string, string> = {
  bls: "#1a4480",
  fred: "#0b3d91",
  census: "#112e51",
  edgar: "#205493",
  "world bank": "#009fda",
  worldbank: "#009fda",
  kalshi: "#00d09c",
  oecd: "#0061a0",
  eurostat: "#003399",
  comtrade: "#418fde",
  fdic: "#003366",
  cms: "#1a4480",
  eia: "#005ea2",
  "usda nass": "#0a5640",
  faa: "#102e5a",
  openfda: "#1a4480",
};

function normalize(name: string): string {
  return name.toLowerCase().trim();
}

export function brandMark(name: string): BrandMark | null {
  const icon = MARKS[normalize(name)];
  if (icon?.path) return { path: icon.path, hex: `#${icon.hex}`, title: icon.title };
  return null;
}

export function brandHex(name: string): string {
  const mark = brandMark(name);
  if (mark) return mark.hex;
  return GOV_HEX[normalize(name)] ?? "var(--accent)";
}

export function monogram(name: string): string {
  const words = name
    .replace(/[^a-zA-Z0-9 ]/g, "")
    .trim()
    .split(/\s+/);
  if (words.length >= 2) return (words[0][0] + words[1][0]).toUpperCase();
  return name.slice(0, 2).toUpperCase();
}
