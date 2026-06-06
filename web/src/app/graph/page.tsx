import { redirect } from "next/navigation";

// /graph has moved to /explore/pyramid. This redirect keeps old links working.
export default function GraphRedirect() {
  redirect("/explore/pyramid");
}
