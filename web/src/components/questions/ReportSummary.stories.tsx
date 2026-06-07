import type { Meta, StoryObj } from "@storybook/react";

import { CoverageBars } from "@/components/questions/CoverageBars";
import { GapMap } from "@/components/questions/GapMap";
import { MethodologyStrip } from "@/components/questions/MethodologyStrip";
import { ReportSummary } from "@/components/questions/ReportSummary";
import { SourceLedger } from "@/components/questions/SourceLedger";
import { TamRangeField } from "@/components/questions/TamRangeField";
import { deriveReportMetrics } from "@/lib/report-metrics";
import type { ConceptQuestionReport } from "@/lib/schemas";
import demoReportJson from "./__fixtures__/demo-report.json";

// The live /report/demo-ai-sales-ops-us payload (64 answers, 27 answered, 37
// gaps) — the same data the PDF was generated from, so Storybook shows the real
// shape, not a toy.
const demoReport = demoReportJson as ConceptQuestionReport;
const demoMetrics = deriveReportMetrics(demoReport);

const meta: Meta<typeof ReportSummary> = {
  title: "Report/ReportSummary",
  component: ReportSummary,
  parameters: { layout: "fullscreen" },
  decorators: [
    (Story) => (
      <div className="mx-auto w-full max-w-[860px] px-8 py-10" style={{ color: "var(--fg-1)" }}>
        <Story />
      </div>
    ),
  ],
};
export default meta;
type Story = StoryObj<typeof ReportSummary>;

// The full executive band over real demo data.
export const FullSummary: Story = {
  args: { report: demoReport },
};

// A concept that resolves to a single method family — the range field has no
// cross-method spread to plot and degrades to an honest line.
export const SingleMethod: Story = {
  args: {
    report: {
      ...demoReport,
      answers: demoReport.answers.filter((a) => !["Q-MS-007", "Q-MS-001"].includes(a.question_id)),
    },
  },
};

// No applicable questions — renders nothing (the QuestionReport shows its own
// empty copy in that case).
export const Empty: Story = {
  args: { report: { ...demoReport, answers: [] } },
};

// --- Individual blocks, for isolated iteration -----------------------------

export const RangeFieldOnly: StoryObj = {
  render: () =>
    demoMetrics.range ? (
      <TamRangeField range={demoMetrics.range} headlineDisplay={demoMetrics.headlineDisplay} />
    ) : (
      <div>no range</div>
    ),
};

export const MethodologyOnly: StoryObj = {
  render: () => <MethodologyStrip method={demoMetrics.method} />,
};

export const CoverageOnly: StoryObj = {
  render: () => <CoverageBars coverage={demoMetrics.coverage} />,
};

export const GapMapOnly: StoryObj = {
  render: () => <GapMap coverage={demoMetrics.coverage} gapTargets={demoMetrics.gapTargets} />,
};

export const SourceLedgerOnly: StoryObj = {
  render: () => <SourceLedger rows={demoMetrics.ledger} />,
};
