// /dashboard — the board surface (PR 3). Library counts, your saved builds
// (sign-in-gated when Clerk is configured), and the audit feed. Degrades
// gracefully with no Clerk keys (notice + public panels, never a crash).
import { DashboardView } from "./DashboardView";

export default function DashboardPage() {
  return <DashboardView />;
}
