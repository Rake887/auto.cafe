import Link from "next/link";
import { redirect } from "next/navigation";
import { requireSession } from "@/lib/admin-session";
import { fetchAdminCalls } from "@/lib/api";
import { AdminHeader } from "@/components/AdminHeader";
import { CallsFeed } from "@/components/CallsFeed";

export const dynamic = "force-dynamic";

const PERIODS = [
  { key: "day", label: "Сутки" },
  { key: "week", label: "Неделя" },
  { key: "all", label: "Всё время" },
];

export default async function AdminCallsPage({
  searchParams,
}: {
  searchParams: Promise<{ [key: string]: string | string[] | undefined }>;
}) {
  const session = await requireSession();
  const { period: rawPeriod } = await searchParams;
  const period =
    typeof rawPeriod === "string" && PERIODS.some((p) => p.key === rawPeriod)
      ? rawPeriod
      : "day";

  const calls = await fetchAdminCalls(session, period);
  if (calls === null) redirect("/admin/login");

  return (
    <main className="mx-auto min-h-dvh w-full max-w-2xl px-5 pt-8 pb-16">
      <AdminHeader
        eyebrow="Вызовы"
        title="Кто звал официанта"
        hint="Гость жмёт кнопку в меню — вызов уходит в чат. Если за полторы минуты никто не нажал «Иду», бот дёргает чат повторно, а вызов помечается просроченным."
      />

      <nav className="mt-5 flex gap-2 overflow-x-auto pb-1" aria-label="Период">
        {PERIODS.map((p) => (
          <Link
            key={p.key}
            href={`/admin/calls?period=${p.key}`}
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

      <CallsFeed calls={calls} />
    </main>
  );
}
