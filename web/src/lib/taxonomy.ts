// Curated typeahead suggestions + format validators for the market-spec step.
//
// This is a STARTER set, not the full NAICS/SOC taxonomy — it exists so a user
// pinning a market gets recognition (pick "Software Developers" from a list)
// instead of recall (type "15-1252" from memory), and so a typo'd code is
// caught before it folds into the state hash and silently scopes the wrong
// market. A free classifier over the full code set is the eventual replacement;
// until then this covers the product's common verticals/personas honestly.

export interface CodeSuggestion {
  code: string;
  label: string;
}

// Common NAICS verticals (tech, financial services, health, the worked-example
// domains in the data bank). Sector ranges (44-45) are valid NAICS.
const NAICS_SUGGESTIONS: CodeSuggestion[] = [
  { code: "5415", label: "Computer Systems Design & Related Services" },
  { code: "541511", label: "Custom Computer Programming Services" },
  { code: "541512", label: "Computer Systems Design Services" },
  { code: "5112", label: "Software Publishers" },
  { code: "511210", label: "Software Publishers" },
  { code: "518210", label: "Data Processing, Hosting & Related Services" },
  { code: "5191", label: "Web Search Portals & Information Services" },
  { code: "5416", label: "Management & Technical Consulting Services" },
  { code: "5417", label: "Scientific Research & Development Services" },
  { code: "524", label: "Insurance Carriers & Related Activities" },
  { code: "5242", label: "Insurance Agencies & Brokerages" },
  { code: "522", label: "Credit Intermediation (Banking)" },
  { code: "523", label: "Securities, Commodities & Investments" },
  { code: "621", label: "Ambulatory Health Care Services" },
  { code: "44-45", label: "Retail Trade" },
  { code: "31-33", label: "Manufacturing" },
];

// Common SOC personas (the people who buy/use the software).
const SOC_SUGGESTIONS: CodeSuggestion[] = [
  { code: "15-1252", label: "Software Developers" },
  { code: "15-1211", label: "Computer Systems Analysts" },
  { code: "15-1244", label: "Network & Systems Administrators" },
  { code: "15-2051", label: "Data Scientists" },
  { code: "41-4012", label: "Sales Reps, Wholesale & Manufacturing" },
  { code: "41-3091", label: "Sales Reps of Services" },
  { code: "13-1111", label: "Management Analysts (Consultants)" },
  { code: "13-2011", label: "Accountants & Auditors" },
  { code: "11-1021", label: "General & Operations Managers" },
  { code: "23-1011", label: "Lawyers" },
  { code: "29-1141", label: "Registered Nurses" },
  { code: "43-9061", label: "Office Clerks, General" },
];

// Common ISO 3166-1 alpha-2 geos (+ EU as a supported aggregate region).
export const ISO_SUGGESTIONS: CodeSuggestion[] = [
  { code: "US", label: "United States" },
  { code: "CA", label: "Canada" },
  { code: "GB", label: "United Kingdom" },
  { code: "DE", label: "Germany" },
  { code: "FR", label: "France" },
  { code: "IN", label: "India" },
  { code: "JP", label: "Japan" },
  { code: "CN", label: "China" },
  { code: "AU", label: "Australia" },
  { code: "BR", label: "Brazil" },
  { code: "EU", label: "European Union" },
];

export function suggestionsFor(system: string): CodeSuggestion[] {
  if (system === "NAICS") return NAICS_SUGGESTIONS;
  if (system === "SOC") return SOC_SUGGESTIONS;
  return [];
}

// null = valid (or empty). Otherwise a short, plain-language format hint.
export function validateCode(system: string, code: string): string | null {
  const c = code.trim();
  if (!c) return null;
  if (system === "NAICS") {
    return /^\d{2,6}$/.test(c) || /^\d{2}-\d{2}$/.test(c)
      ? null
      : "NAICS is 2–6 digits (e.g. 5415)";
  }
  if (system === "SOC") {
    return /^\d{2}-\d{4}$/.test(c) ? null : "SOC looks like 15-1252";
  }
  return null;
}

export function validateIso(code: string): string | null {
  const c = code.trim().toUpperCase();
  if (!c) return null;
  return /^[A-Z]{2}$/.test(c) ? null : "ISO is a 2-letter code (US, GB)";
}

// Auto-fill the label when a user picks a known code from the typeahead.
export function labelForCode(system: string, code: string): string | undefined {
  return suggestionsFor(system).find((s) => s.code === code.trim())?.label;
}
