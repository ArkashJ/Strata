import { PrimitiveDetailView } from "@/components/primitive/PrimitiveDetailView";

// Next 16: `params` is a Promise — await before reading. See /c/[slug] note.
export default async function PrimitiveDetailPage({
  params,
}: {
  params: Promise<{ slug: string }>;
}) {
  const { slug } = await params;
  return <PrimitiveDetailView slug={slug} />;
}
