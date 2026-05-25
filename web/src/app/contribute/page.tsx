export default function ContributePage() {
  return (
    <main className="flex-1 flex flex-col items-center justify-center gap-4 px-8">
      <h1 className="display text-[40px] text-[var(--fg-1)]">Contribute</h1>
      <p className="text-[15px] text-[var(--fg-3)] max-w-[480px] text-center">
        PR-based contribution flow, validator pipeline, and web form for
        annotations. Coming in v0.5.
      </p>
      <a
        href="/"
        className="mt-2 text-[13px] text-[var(--accent)] hover:underline"
      >
        Back to search
      </a>
    </main>
  );
}
