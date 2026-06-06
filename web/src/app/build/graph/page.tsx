// /build/graph folded into the unified build workshop as its "Compose a graph"
// mode (restructure plan §2). The old route now redirects so shared links survive.
import { redirect } from "next/navigation";

export default function GraphBuilderPage() {
  redirect("/build?mode=graph");
}
