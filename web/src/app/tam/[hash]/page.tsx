// Frozen TAM artifact (U6, U11). The route segment is the canonical state hash —
// the "permanent URL" promise. The server component only unwraps the Next 16
// params promise; the data fetch + render happen client-side in TamDetailView so
// the tanstack cache, Copy/Export interactions, and the shared ScenarioGraph
// (a client component) all live in one place.
import { TamDetailView } from "@/components/tam/TamDetailView";

type Props = { params: Promise<{ hash: string }> };

export default async function TamPage({ params }: Props) {
  const { hash } = await params;
  return <TamDetailView hash={hash} />;
}
