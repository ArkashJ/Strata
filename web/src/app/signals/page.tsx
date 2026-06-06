import { redirect } from "next/navigation";

// /signals has moved to /explore/signals. This redirect keeps old links working.
export default function SignalsRedirect() {
  redirect("/explore/signals");
}
