import Link from "next/link";
import { redirect } from "next/navigation";
import { fetchPoints } from "@/lib/api";
import { requireSession } from "@/lib/admin-session";
import { QrSheet } from "@/components/QrSheet";

// Адрес туннеля меняется — страницу печати кэшировать нельзя
export const dynamic = "force-dynamic";

export default async function QrPage() {
  const session = await requireSession();
  const data = await fetchPoints(session);
  if (data === null) redirect("/admin/login");

  const host = data.site_url?.replace(/^https?:\/\//, "") ?? null;

  return (
    <main className="mx-auto w-full max-w-3xl px-5 py-8 print:max-w-none print:px-0 print:py-0">
      <header className="print:hidden">
        <p className="text-xs font-semibold tracking-[0.14em] text-ink-faint uppercase">
          Наклейки на столы
        </p>
        <h1 className="mt-1.5 text-2xl font-bold text-ink">QR-коды столов</h1>
        <p className="mt-2 text-sm text-ink-muted">
          Адрес под кодом напечатан намеренно: если наклейку подменят чужим QR,
          гость сможет это заметить.
        </p>

        {data.site_url === null && (
          <div className="mt-4 rounded-2xl bg-muted px-4 py-3 text-sm text-ink-muted">
            Публичный адрес не поднят, поэтому ссылки в кодах вели бы в никуда.
            Запустите туннель и обновите страницу:
            <code className="mt-2 block text-xs">
              docker compose --profile tunnel-cf up -d cloudflared
            </code>
          </div>
        )}

        <div className="mt-5 flex gap-2">
          <Link
            href="/admin"
            className="rounded-full bg-muted px-4 py-2 text-sm text-ink-muted"
          >
            ← Кабинет
          </Link>
          <Link
            href="/admin/tables"
            className="rounded-full bg-muted px-4 py-2 text-sm text-ink-muted"
          >
            Столы
          </Link>
        </div>
      </header>

      {data.site_url !== null && (
        <QrSheet zones={data.zones} points={data.points} host={host} />
      )}
    </main>
  );
}
