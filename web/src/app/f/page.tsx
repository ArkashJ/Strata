import { redirect } from "next/navigation";

// /f has moved to /explore/frameworks. This redirect keeps old links working.
export default function FrameworksListRedirect() {
  redirect("/explore/frameworks");
}
