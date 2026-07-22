import Link from "next/link";

/** Шапка раздела кабинета: путь назад одинаков везде, чтобы владелец не искал
 *  выход из каждого раздела заново. */
export function AdminHeader({
  eyebrow,
  title,
  hint,
}: {
  eyebrow: string;
  title: string;
  hint?: string;
}) {
  return (
    <header>
      <Link
        href="/admin"
        className="inline-flex rounded-full bg-muted px-4 py-2 text-sm text-ink-muted"
      >
        ← Кабинет
      </Link>
      <p className="mt-4 text-xs font-semibold tracking-[0.14em] text-ink-faint uppercase">
        {eyebrow}
      </p>
      <h1 className="mt-1.5 text-2xl font-bold text-ink">{title}</h1>
      {hint && <p className="mt-2 text-sm text-ink-muted">{hint}</p>}
    </header>
  );
}
