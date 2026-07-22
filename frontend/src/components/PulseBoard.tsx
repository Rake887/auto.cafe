"use client";

import Link from "next/link";
import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { adminMutate } from "@/lib/api";
import { formatPrice, plural } from "@/lib/format";
import { useAdminAction } from "@/lib/use-admin-action";
import type { OpenCall, OpenVisit, Pulse } from "@/lib/types";

// Смена идёт минутами: реже — и владелец смотрит на прошлое
const REFRESH_MS = 15_000;
// Дольше этого непринятый заказ — уже не «ещё не успели», а «проспали»
const LATE_MINUTES = 10;

/** Первый экран кабинета: не деньги за неделю, а то, что горит сейчас. */
export function PulseBoard({
  pulse,
  acceptingOrders,
}: {
  pulse: Pulse;
  acceptingOrders: boolean;
}) {
  const router = useRouter();
  const { error, busy, run } = useAdminAction();

  useEffect(() => {
    const timer = setInterval(() => router.refresh(), REFRESH_MS);
    return () => clearInterval(timer);
  }, [router]);

  const inProgress = pulse.orders_new + pulse.orders_cooking + pulse.orders_ready;
  const late =
    pulse.oldest_new_minutes !== null && pulse.oldest_new_minutes >= LATE_MINUTES;
  const quiet =
    inProgress === 0 &&
    pulse.open_calls.length === 0 &&
    pulse.open_visits.length === 0 &&
    pulse.unresolved_reviews === 0;

  return (
    <section className="mt-5" aria-label="Сейчас в зале">
      <div className="flex items-center justify-between gap-3">
        <h2 className="text-xs font-semibold tracking-[0.14em] text-ink-faint uppercase">
          Сейчас в зале
        </h2>
        <button
          type="button"
          disabled={busy}
          onClick={() =>
            run(() =>
              adminMutate("/admin/branch", {
                method: "PATCH",
                body: JSON.stringify({ accepting_orders: !acceptingOrders }),
              }),
            )
          }
          className={`h-8 shrink-0 rounded-full px-3 text-xs font-semibold disabled:opacity-60 ${
            acceptingOrders
              ? "bg-muted text-ink-muted"
              : "bg-danger text-white"
          }`}
        >
          {acceptingOrders ? "Принимаем заказы" : "Приём выключен"}
        </button>
      </div>

      {error !== null && (
        <p className="mt-2 rounded-xl bg-muted px-3 py-2 text-sm text-danger">
          {error}
        </p>
      )}

      {quiet ? (
        <p className="mt-2 rounded-2xl bg-muted px-4 py-3 text-sm text-ink-muted">
          Тихо: незакрытых заказов и вызовов нет.
        </p>
      ) : (
        <div className="mt-2 grid grid-cols-3 gap-2">
          <Tile
            label="Не приняли"
            value={pulse.orders_new}
            hint={
              pulse.oldest_new_minutes !== null
                ? `самый старый ${pulse.oldest_new_minutes} мин`
                : undefined
            }
            danger={late}
          />
          <Tile label="Готовят" value={pulse.orders_cooking} />
          <Tile label="Готово, ждёт" value={pulse.orders_ready} />
        </div>
      )}

      {pulse.open_calls.length > 0 && (
        <ul className="mt-2 space-y-2">
          {pulse.open_calls.map((call) => (
            <CallRow
              key={call.id}
              call={call}
              busy={busy}
              onResolve={() =>
                run(() =>
                  adminMutate(`/admin/calls/${call.id}/resolve`, {
                    method: "POST",
                  }),
                )
              }
            />
          ))}
        </ul>
      )}

      {pulse.open_visits.length > 0 && (
        <ul className="mt-2 space-y-2">
          {pulse.open_visits.map((visit) => (
            <VisitRow
              key={visit.id}
              visit={visit}
              busy={busy}
              onClose={() =>
                run(() =>
                  adminMutate(`/admin/visits/${visit.id}/close`, {
                    method: "POST",
                  }),
                )
              }
            />
          ))}
        </ul>
      )}

      {pulse.unresolved_reviews > 0 && (
        <Link
          href="/admin/reviews"
          className="mt-2 flex items-center justify-between rounded-2xl bg-danger/10 px-4 py-3 text-sm font-medium text-danger"
        >
          <span>
            {pulse.unresolved_reviews}{" "}
            {plural(
              pulse.unresolved_reviews,
              "жалоба ждёт",
              "жалобы ждут",
              "жалоб ждут",
            )}{" "}
            разбора
          </span>
          <span aria-hidden>→</span>
        </Link>
      )}
    </section>
  );
}

/** Стол, по которому ещё не закрыли счёт: официант несёт один счёт на визит. */
function VisitRow({
  visit,
  busy,
  onClose,
}: {
  visit: OpenVisit;
  busy: boolean;
  onClose: () => void;
}) {
  return (
    <li
      className={`flex items-center gap-3 rounded-2xl px-4 py-3 ${
        visit.confirmed ? "bg-raised shadow-sm" : "bg-danger/10"
      }`}
    >
      <span aria-hidden>{visit.confirmed ? "🧾" : "🪑"}</span>
      <div className="min-w-0 flex-1">
        <p className="truncate text-sm font-medium text-ink">
          {visit.point_label}
          <span className="text-ink-faint"> · {visit.zone_name}</span>
        </p>
        <p
          className={`text-xs ${
            visit.confirmed ? "text-ink-faint" : "text-danger"
          }`}
        >
          {visit.orders} {plural(visit.orders, "заказ", "заказа", "заказов")} ·{" "}
          {formatPrice(visit.total)}
          {!visit.confirmed && " · ждёт подтверждения стола"}
          {visit.has_remote && " · ⚠️ заказ вне зала"}
        </p>
      </div>
      <button
        type="button"
        disabled={busy}
        onClick={onClose}
        className="h-9 shrink-0 rounded-full bg-muted px-3 text-sm text-ink disabled:opacity-60"
      >
        Счёт закрыт
      </button>
    </li>
  );
}

function Tile({
  label,
  value,
  hint,
  danger,
}: {
  label: string;
  value: number;
  hint?: string;
  danger?: boolean;
}) {
  return (
    <div
      className={`rounded-2xl border p-3 ${
        danger && value > 0
          ? "border-danger/40 bg-danger/10"
          : "border-line/60 bg-raised"
      }`}
    >
      <p className="text-xs font-semibold text-ink-muted">{label}</p>
      <p
        className={`mt-1 text-2xl font-extrabold tabular-nums ${
          danger && value > 0 ? "text-danger" : "text-ink"
        }`}
      >
        {value}
      </p>
      {hint && <p className="mt-0.5 text-[11px] text-ink-faint">{hint}</p>}
    </div>
  );
}

function CallRow({
  call,
  busy,
  onResolve,
}: {
  call: OpenCall;
  busy: boolean;
  onResolve: () => void;
}) {
  const waited = Math.floor(call.waiting_seconds / 60);
  return (
    <li
      className={`flex items-center gap-3 rounded-2xl px-4 py-3 ${
        call.escalated ? "bg-danger/10" : "bg-raised shadow-sm"
      }`}
    >
      <span aria-hidden>🔔</span>
      <div className="min-w-0 flex-1">
        <p className="truncate text-sm font-medium text-ink">
          {call.point_label}
          <span className="text-ink-faint"> · {call.zone_name}</span>
        </p>
        <p
          className={`text-xs ${call.escalated ? "text-danger" : "text-ink-faint"}`}
        >
          зовёт официанта{" "}
          {waited < 1 ? `${call.waiting_seconds} с` : `${waited} мин`}
          {call.escalated && " · просрочено"}
          {call.comment && ` · ${call.comment}`}
        </p>
      </div>
      <button
        type="button"
        disabled={busy}
        onClick={onResolve}
        className="h-9 shrink-0 rounded-full bg-muted px-3 text-sm text-ink disabled:opacity-60"
      >
        Закрыть
      </button>
    </li>
  );
}
