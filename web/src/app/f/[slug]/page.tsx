import { FrameworkDetailView } from "@/components/framework/FrameworkDetailView";

// Next 16: `params` is a Promise — await before reading. See /c/[slug] note.
export default async function FrameworkDetailPage({
  params,
}: {
  params: Promise<{ slug: string }>;
}) {
  const { slug } = await params;
  return <FrameworkDetailView slug={slug} />;
}
