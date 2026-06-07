import { AppShell } from "@/components/shell/AppShell";
import { clerkEnabled } from "@/lib/clerk";
import { Providers } from "@/lib/providers";
import { ClerkProvider } from "@clerk/nextjs";
import type { Metadata } from "next";
import { Geist, Geist_Mono, Instrument_Serif } from "next/font/google";
import "./globals.css";

const geistSans = Geist({
  variable: "--font-ui",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-mono",
  subsets: ["latin"],
});

const instrumentSerif = Instrument_Serif({
  variable: "--font-display",
  subsets: ["latin"],
  weight: "400",
});

export const metadata: Metadata = {
  // Base origin so relative OpenGraph image URLs (e.g. /tam/[hash]'s og image)
  // resolve to absolute URLs for social/unfurl bots.
  metadataBase: new URL(process.env.NEXT_PUBLIC_SITE_URL ?? "https://stratabank.vercel.app"),
  title: "Strata — Defensible TAM",
  description:
    "Open-source community-curated market sizing. Primitives, frameworks, and a chain of custody you can paste in a memo.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  const tree = (
    <html
      lang="en"
      // The no-flash script below mutates <html> (dark class + color-scheme)
      // before React hydrates, so the server/client attributes differ by design.
      suppressHydrationWarning
      className={`${geistSans.variable} ${geistMono.variable} ${instrumentSerif.variable} h-full antialiased`}
    >
      <body className="min-h-full bg-[var(--bg-0)] text-[var(--fg-1)]">
        {/*
         * No-flash theme bootstrap: runs synchronously before the body paints,
         * so a returning dark-mode user never sees a light flash. Light is the
         * default — dark only when the user explicitly opted in (strata-theme).
         */}
        <script
          // biome-ignore lint/security/noDangerouslySetInnerHtml: must run pre-hydration before first paint
          dangerouslySetInnerHTML={{
            __html:
              "(function(){try{var d=localStorage.getItem('strata-theme')==='dark';var e=document.documentElement;e.classList.toggle('dark',d);e.style.colorScheme=d?'dark':'light';}catch(e){}})();",
          }}
        />
        <Providers>
          <AppShell>{children}</AppShell>
        </Providers>
      </body>
    </html>
  );

  // Only mount ClerkProvider when a publishable key is configured. Wrapping it
  // unconditionally throws at build/runtime when the key is absent (prod today),
  // so without keys we render the app exactly as before.
  return clerkEnabled ? <ClerkProvider>{tree}</ClerkProvider> : tree;
}
