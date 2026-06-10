// The web app is retired in favor of the CLI + MCP surfaces — the homepage is
// now always the public marketing landing (the full app lives on the
// `frontend-archive` branch / `frontend-archive-2026-06-10` tag).
import { NightCanvas } from "@/components/landing/NightCanvas";
import { PublicLanding } from "@/components/landing/PublicLanding";

export default function Home() {
  return (
    <NightCanvas>
      <PublicLanding />
    </NightCanvas>
  );
}
