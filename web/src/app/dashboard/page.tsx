// /dashboard is now /bank. Permanent redirect so existing links survive.
import { redirect } from "next/navigation";

export default function DashboardPage() {
  redirect("/bank");
}
