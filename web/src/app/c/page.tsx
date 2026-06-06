import { redirect } from "next/navigation";

// /c has moved to /explore/concepts. This redirect keeps old links working.
export default function ConceptsListRedirect() {
  redirect("/explore/concepts");
}
