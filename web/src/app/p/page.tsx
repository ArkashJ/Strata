import { redirect } from "next/navigation";

// /p has moved to /explore/primitives. This redirect keeps old links working.
export default function PrimitivesListRedirect() {
  redirect("/explore/primitives");
}
