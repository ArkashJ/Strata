import { redirect } from "next/navigation";

// /explore has no content of its own — Concepts is the default tab.
export default function ExploreIndex() {
  redirect("/explore/concepts");
}
