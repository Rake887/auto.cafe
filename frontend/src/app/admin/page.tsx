import Link from "next/link";
import { redirect } from "next/navigation";
import { fetchAdminBranch, fetchAdminStats, fetchPulse } from "@/lib/api";
import { requireSession } from "@/lib/admin-session";
import { LogoutButton } from "@/components/LogoutButton";
import { PulseBoard } from "@/components/PulseBoard";
import { formatPrice, plural } from "@/lib/format";
import type { Bucket, DishStat, StaffStat } from "@/lib/types";

// Цифры должны быть свежими на каждый заход, кэш здесь вреден
export const dynamic = "force-dynamic";

const PERIODS = [
  { key: "day", label: "Сутки" },
  { key: "week", label: "Неделя" },
  { key: "all", label: "Всё время" },
];

// Порядок — по частоте использования: меню и заказы владелец открывает каждый
// день, настройки — раз в полгода
const SECTIONS = [
  { href: "/admin/menu", label: "Меню и цены", icon: "📋", primary: true },
  { href: "/admin/orders", label: "Заказы", icon: "🧾", primary: true },
  { href: "/admin/calls", label: "Вызовы", icon: "🔔" },
  { href: "/admin/reviews", label: "Отзывы", icon: "⭐" },
  { href: "/admin/staff", label: "Персонал", icon: "👥" },
  { href: "/admin/tables", label: "Столы", icon: "🪑" },
  { href: "/admin/qr", label: "QR для печати", icon: "🖨️" },
  { href: "/admin/settings", label: "Настройки", icon: "⚙️" },
];

export default async function AdminPage({
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

  const [stats, pulse, branch] = await Promise.all([
    fetchAdminStats(session, period),
    fetchPulse(session),
    fetchAdminBranch(session),
  ]);
  // сессия протухла или отозвана — просим войти заново
  if (stats === null) redirect("/admin/login");

  const { totals } = stats;

  return (
    <main className="mx-auto min-h-dvh w-full max-w-2xl px-5 pt-8 pb-12">
      <header className="flex items-start justify-between gap-3">
        <div>
          <div className="flex items-center gap-2">
            <span className="flex h-6 items-center rounded-full bg-accent/15 px-2.5 text-[10px] font-extrabold tracking-wider text-accent uppercase">
              Кабинет
            </span>
            <span className="text-xs text-ink-faint">Тараз</span>
          </div>
          <h1 className="mt-1 text-2xl font-extrabold text-ink">
            {stats.branch_name}
          </h1>
        </div>
        <LogoutButton />
      </header>

      {pulse !== null && (
        <PulseBoard
          pulse={pulse}
          acceptingOrders={branch?.accepting_orders ?? true}
        />
      )}

      <nav className="mt-5 grid grid-cols-2 gap-3" aria-label="Разделы кабинета">
        {SECTIONS.map((s) => (
          <Link
            key={s.href}
            href={s.href}
            className={`flex h-13 items-center justify-center gap-2 rounded-2xl text-sm font-semibold transition active:scale-95 ${
              s.primary
                ? "bg-accent text-on-accent shadow-md hover:bg-accent-strong"
                : "border border-line bg-raised text-ink shadow-xs hover:bg-muted"
            }`}
          >
            <span>{s.icon}</span> {s.label}
          </Link>
        ))}
      </nav>

      <nav className="mt-5 flex gap-2 overflow-x-auto pb-1" aria-label="Период">
        {PERIODS.map((p) => (
          <Link
            key={p.key}
            href={`/admin?period=${p.key}`}
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

      <section className="mt-6 grid grid-cols-2 gap-3">
        <Metric title="Выручка" value={formatPrice(totals.revenue)} icon="💰" accent />
        <Metric
          title="Заказов"
          value={String(totals.orders)}
          icon="📦"
          hint={
            totals.in_progress > 0 ? `⏳ ${totals.in_progress} в работе` : undefined
          }
        />
        <Metric title="Средний чек" value={formatPrice(totals.average_check)} icon="📊" />
        <Metric
          title="Оценка гостей"
          value={stats.rating_avg === null ? "—" : `${stats.rating_avg} из 5`}
          icon="⭐"
          hint={
            stats.rating_count > 0
              ? `${stats.rating_count} ${plural(stats.rating_count, "оценка", "оценки", "оценок")}`
              : "ещё не оценивали"
          }
        />
        <Metric
          title="Скорость подачи"
          value={
            totals.avg_minutes_to_served === null
              ? "—"
              : `${totals.avg_minutes_to_served} мин`
          }
          icon="⚡"
          hint={totals.avg_minutes_to_served === null ? "нет данных" : "в среднем"}
        />
      </section>

      {totals.food_cost_percent !== null && (
        <Panel title="Сколько остаётся заведению">
          <div className="flex items-baseline justify-between gap-3">
            <div>
              <p className="text-xs font-semibold text-ink-muted">
                Себестоимость
              </p>
              <p
                className={`mt-1 text-xl font-extrabold tabular-nums ${
                  totals.food_cost_percent > 40 ? "text-danger" : "text-ink"
                }`}
              >
                {totals.food_cost_percent}%
              </p>
            </div>
            <div className="text-right">
              <p className="text-xs font-semibold text-ink-muted">Прибыль</p>
              <p className="mt-1 text-xl font-extrabold text-accent tabular-nums">
                {formatPrice(totals.profit)}
              </p>
            </div>
          </div>
          {/* без этой оговорки цифра выглядела бы точной, хотя посчитана
              по части меню — а решения по ней принимают денежные */}
          <p className="mt-3 text-xs text-ink-faint">
            {totals.costed_share >= 100
              ? "Посчитано по всем проданным порциям."
              : `Посчитано только по ${totals.costed_share}% проданных порций — у остальных блюд себестоимость не заполнена.`}
          </p>
        </Panel>
      )}

      {stats.top_profit.length > 0 && (
        <Panel
          title="Что приносит больше всего денег"
          hint="Не то же самое, что популярное: дешёвое блюдо можно продать сто раз и заработать меньше, чем на десяти дорогих."
        >
          <ol className="space-y-3">
            {stats.top_profit.map((dish, i) => (
              <DishBar
                key={dish.name}
                dish={dish}
                place={i + 1}
                max={stats.top_profit[0].profit ?? 1}
                byProfit
              />
            ))}
          </ol>
        </Panel>
      )}

      <Panel title="Что заказывают чаще всего">
        {stats.top_dishes.length === 0 ? (
          <Empty>За этот период заказов не было.</Empty>
        ) : (
          <ol className="space-y-3">
            {stats.top_dishes.map((dish, i) => (
              <DishBar
                key={dish.name}
                dish={dish}
                place={i + 1}
                max={stats.top_dishes[0].qty}
              />
            ))}
          </ol>
        )}
      </Panel>

      {stats.by_hour.length > 0 && (
        <Panel title="Когда заказывают">
          <BucketChart buckets={stats.by_hour} />
        </Panel>
      )}

      {stats.by_weekday.length > 1 && (
        <Panel title="По дням недели">
          <BucketChart buckets={stats.by_weekday} />
        </Panel>
      )}

      {stats.by_zone.length > 1 && (
        <Panel title="По залам">
          <ul className="divide-y divide-line">
            {stats.by_zone.map((zone) => (
              <li key={zone.name} className="py-2.5 first:pt-0">
                <div className="flex items-baseline gap-3">
                  <p className="min-w-0 flex-1 truncate text-ink">{zone.name}</p>
                  <p className="shrink-0 font-medium text-ink tabular-nums">
                    {formatPrice(zone.revenue)}
                  </p>
                </div>
                <p className="mt-0.5 text-xs text-ink-faint">
                  {zone.orders} {plural(zone.orders, "заказ", "заказа", "заказов")}
                  {" · средний чек "}
                  {formatPrice(zone.average_check)}
                </p>
              </li>
            ))}
          </ul>
        </Panel>
      )}

      <Panel title="Официанты">
        <StaffTable
          rows={stats.waiters}
          empty="Никто ещё не нажимал «Обслуживаю»."
          countLabel="отнёс"
        />
      </Panel>

      <Panel title="Повара">
        <StaffTable
          rows={stats.cooks}
          empty="Никто ещё не принимал заказы в работу."
          countLabel="принял"
        />
      </Panel>

      {/* Объясняем разрыв между общей выручкой и суммами по персоналу:
          заказы, до которых на кухне не дошли руки. */}
      {totals.untouched > 0 && (
        <p className="mt-6 rounded-2xl bg-muted px-4 py-3 text-sm text-ink-muted">
          Никто не взял в работу {totals.untouched}{" "}
          {plural(totals.untouched, "заказ", "заказа", "заказов")} на{" "}
          {formatPrice(totals.untouched_revenue)} — в чате их не приняли. На
          столько суммы по персоналу и меньше общей выручки.
        </p>
      )}


      {totals.cancelled > 0 && (
        <p className="mt-3 text-sm text-ink-faint">
          Отменённых заказов за период: {totals.cancelled}. В выручке они не
          учтены.
        </p>
      )}
    </main>
  );
}

function Metric({
  title,
  value,
  hint,
  icon,
  accent,
}: {
  title: string;
  value: string;
  hint?: string;
  icon?: string;
  accent?: boolean;
}) {
  return (
    <div className="rounded-2xl bg-raised p-4 border border-line/60 shadow-xs">
      <div className="flex items-center justify-between">
        <p className="text-xs font-semibold text-ink-muted">{title}</p>
        {icon && <span className="text-base">{icon}</span>}
      </div>
      <p
        className={`mt-1.5 text-xl font-extrabold tabular-nums ${
          accent ? "text-accent" : "text-ink"
        }`}
      >
        {value}
      </p>
      {hint && <p className="mt-0.5 text-xs font-medium text-ink-faint">{hint}</p>}
    </div>
  );
}

function Panel({
  title,
  hint,
  children,
}: {
  title: string;
  hint?: string;
  children: React.ReactNode;
}) {
  return (
    <section className="mt-6">
      <h2 className="text-lg font-bold text-ink">{title}</h2>
      {hint && <p className="mt-1 text-sm text-ink-faint">{hint}</p>}
      <div className="mt-3 rounded-2xl bg-raised p-4 shadow-sm">{children}</div>
    </section>
  );
}

/** Столбики без библиотек графиков: высота в процентах от максимума. */
function BucketChart({ buckets }: { buckets: Bucket[] }) {
  const max = Math.max(...buckets.map((b) => b.orders));
  return (
    <div className="flex items-end gap-1.5 overflow-x-auto">
      {buckets.map((b) => (
        <div key={b.label} className="flex min-w-9 flex-1 flex-col items-center gap-1">
          <span className="text-xs text-ink-faint tabular-nums">{b.orders}</span>
          <div
            className="w-full rounded-t bg-accent"
            style={{ height: `${Math.max(6, (b.orders / max) * 90)}px` }}
            title={`${b.label}: ${b.orders} заказов на ${formatPrice(b.revenue)}`}
          />
          <span className="text-[11px] whitespace-nowrap text-ink-muted">
            {b.label}
          </span>
        </div>
      ))}
    </div>
  );
}

function Empty({ children }: { children: React.ReactNode }) {
  return <p className="py-2 text-sm text-ink-faint">{children}</p>;
}

/** Строка топа блюд: полоска даёт увидеть разрыв между позициями сразу.
 *  byProfit — то же самое, но длина полоски и правая цифра про заработок. */
function DishBar({
  dish,
  place,
  max,
  byProfit,
}: {
  dish: DishStat;
  place: number;
  max: number;
  byProfit?: boolean;
}) {
  const value = byProfit ? (dish.profit ?? 0) : dish.qty;
  return (
    <li>
      <div className="flex items-baseline gap-3">
        <span className="w-5 shrink-0 text-sm text-ink-faint tabular-nums">
          {place}
        </span>
        <span className="min-w-0 flex-1 truncate text-ink">{dish.name}</span>
        <span className="shrink-0 font-medium text-ink tabular-nums">
          {formatPrice(byProfit ? (dish.profit ?? 0) : dish.revenue)}
        </span>
      </div>
      <div className="mt-1.5 ml-8 flex items-center gap-3">
        <div className="h-1.5 flex-1 rounded-full bg-muted">
          <div
            className="h-full rounded-full bg-accent"
            style={{ width: `${Math.max(4, (value / max) * 100)}%` }}
          />
        </div>
        <span className="shrink-0 text-xs text-ink-faint tabular-nums">
          {dish.qty} {plural(dish.qty, "порция", "порции", "порций")}
          {byProfit && ` · ${formatPrice(dish.revenue)} выручки`}
        </span>
      </div>
    </li>
  );
}

function StaffTable({
  rows,
  empty,
  countLabel,
}: {
  rows: StaffStat[];
  empty: string;
  countLabel: string;
}) {
  if (rows.length === 0) return <Empty>{empty}</Empty>;
  return (
    <ul className="divide-y divide-line">
      {rows.map((row) => (
        <li key={row.name} className="py-2.5 first:pt-0">
          <div className="flex items-baseline gap-3">
            <p className="min-w-0 flex-1 truncate text-ink">{row.name}</p>
            <p className="shrink-0 font-medium text-ink tabular-nums">
              {formatPrice(row.revenue)}
            </p>
          </div>
          <p className="mt-0.5 text-xs text-ink-faint">
            {/* роль не дублируем, если она уже вписана в имя сотрудника */}
            {row.role && !row.name.toLowerCase().includes(row.role)
              ? `${row.role} · `
              : ""}
            {countLabel} {row.orders}{" "}
            {plural(row.orders, "заказ", "заказа", "заказов")}
          </p>
        </li>
      ))}
    </ul>
  );
}
