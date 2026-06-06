"use client";

// Client owner of the question-report query (mirrors ConceptDetailView): fetch,
// then hand the validated ConceptQuestionReport to the print-first QuestionReport
// renderer. Loading / error / 404 degrade honestly.

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";

import { QuestionReport } from "@/components/questions/QuestionReport";
import { ErrorState } from "@/components/ui/ErrorState";
import { Skeleton } from "@/components/ui/Skeleton";
import { questionReportQuery } from "@/lib/queries";

export function QuestionReportView({ slug }: { slug: string }) {
  const report = useQuery(questionReportQuery(slug));

  if (report.isPending) {
    return (
      <main className="mx-auto w-full max-w-[860px] px-8 py-10">
        <Skeleton className="h-[120px]" />
        <div className="mt-7 flex flex-col gap-4">
          <Skeleton className="h-[140px]" />
          <Skeleton className="h-[140px]" />
        </div>
      </main>
    );
  }

  if (report.isError) {
    return (
      <main className="mx-auto w-full max-w-[860px] px-8 py-10">
        <Link
          href={`/c/${slug}`}
          className="text-[13px] text-[var(--fg-3)] transition-colors hover:text-[var(--fg-1)]"
        >
          ← Back to concept
        </Link>
        <div className="mt-6">
          <ErrorState error={report.error} onRetry={() => report.refetch()} />
        </div>
      </main>
    );
  }

  return <QuestionReport report={report.data} />;
}
