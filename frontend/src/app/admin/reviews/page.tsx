import Link from "next/link";
import { redirect } from "next/navigation";
import { requireSession } from "@/lib/admin-session";
import { fetchAdminReviews } from "@/lib/api";
import { AdminHeader } from "@/components/AdminHeader";
import { ReviewsFeed } from "@/components/ReviewsFeed";

export const dynamic = "force-dynamic";

const PERIODS = [
  { key: "day", label: "Сутки" },
  { key: "week", label: "Неделя" },
  { key: "all", label: "Всё время" },
];

export default async function AdminReviewsPage({
  searchParams,
}: {
  searchParams: Promise<{ [key: string]: string | string[] | undefined }>;
}) {
  const session = await requireSession();
  const { period: rawPeriod } = await searchParams;
  const period =
    typeof rawPeriod === "string" && PERIODS.some((p) => p.key === rawPeriod)
      ? rawPeriod
      : "week";

  const reviews = await fetchAdminReviews(session, period);
  if (reviews === null) redirect("/admin/login");

  return (
    <main className="mx-auto min-h-dvh w-full max-w-2xl px-5 pt-8 pb-16">
      <AdminHeader
        eyebrow="Отзывы"
        title="Что говорят гости"
        hint="Гость ставит оценку после подачи заказа. Довольного зовём оставить отзыв на картах, недовольного — рассказать, что не так; такая жалоба сразу уходит в чат заведения."
      />

      <nav className="mt-5 flex gap-2 overflow-x-auto pb-1" aria-label="Период">
        {PERIODS.map((p) => (
          <Link
            key={p.key}
            href={`/admin/reviews?period=${p.key}`}
            aria-current={p.key === period ? "page" : undefined}
            className={`rounded-full px-4 py-2 text-xs font-bold transition whitespace-nowrap ${
              p.key === period
                ? "bg-ink text-surface shadow-xs dark:bg-raised dark:text-ink"
                : "bg-muted text-ink-muted hover:bg-line/70"
            }`}
          >
            {p.label}
          </Link>
        ))}
      </nav>

      <ReviewsFeed reviews={reviews} />
    </main>
  );
}
