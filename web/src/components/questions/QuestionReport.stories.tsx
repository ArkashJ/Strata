import type { Meta, StoryObj } from "@storybook/react";

import { QuestionReport } from "@/components/questions/QuestionReport";
import type { ConceptQuestionReport } from "@/lib/schemas";
import demoReportJson from "./__fixtures__/demo-report.json";

// Full report over the live /report/demo-ai-sales-ops-us payload — the same
// data the PDF is generated from. This is the page that print-to-PDF captures.
const demoReport = demoReportJson as ConceptQuestionReport;

const meta: Meta<typeof QuestionReport> = {
  title: "Report/QuestionReport",
  component: QuestionReport,
  parameters: { layout: "fullscreen" },
};
export default meta;
type Story = StoryObj<typeof QuestionReport>;

export const Full: Story = {
  args: { report: demoReport },
};
