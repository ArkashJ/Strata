import { QuestionReportView } from "@/components/questions/QuestionReportView";

// Next 16: dynamic-route `params` is a Promise — await it in the server
// component, then hand the slug to a client view that owns the query. Typed
// explicitly (not via the generated PageProps helper) so `tsc --noEmit` passes
// without a prior `next build` populating .next/types. Nested under
// /c/[slug]/questions to keep the report adjacent to the concept it answers.
export default async function ConceptQuestionsPage({
  params,
}: {
  params: Promise<{ slug: string }>;
}) {
  const { slug } = await params;
  return <QuestionReportView slug={slug} />;
}
