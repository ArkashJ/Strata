import { ConceptDetailView } from "@/components/concept/ConceptDetailView";

// Next 16: dynamic-route `params` is a Promise — await it in the server
// component, then hand the slug to a client view that owns the query. Typed
// explicitly (not via the generated PageProps helper) so `tsc --noEmit` passes
// without a prior `next build` populating .next/types.
export default async function ConceptDetailPage({
  params,
}: {
  params: Promise<{ slug: string }>;
}) {
  const { slug } = await params;
  return <ConceptDetailView slug={slug} />;
}
