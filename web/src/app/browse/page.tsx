import { redirect } from "next/navigation";

// /browse has moved to /explore/tams. This redirect keeps old links working.
export default function BrowseRedirect() {
  redirect("/explore/tams");
}
