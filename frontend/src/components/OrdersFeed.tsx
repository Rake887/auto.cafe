"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { adminMutate } from "@/lib/api";
import { formatElapsed, formatPrice } from "@/lib/format";
import { useAdminAction } from "@/lib/use-admin-action";
import type { AdminOrder, OrderStatus } from "@/lib/types";

// Заказ живёт минутами: реже — и владелец смотрит на вчерашний экран
const REFRESH_MS = 20_000;

const STATUS: Record<OrderStatus, { label: string; className: string }> = {
  new: { label: "Новый", className: "bg-danger/15 text-danger" },
  accepted: { label: "Готовят", className: "bg-accent/15 text-accent" },
  ready: { label: "Готов", className: "bg-accent/15 text-accent" },
  served: { label: "Обслужен", className: "bg-muted text-ink-muted" },
  cancelled: { label: "Отменён", className: "bg-muted text-ink-faint" },
};

/** Отменить можно только то, что ещё не отдано гостю. */
const CANCELLABLE: OrderStatus[] = ["new", "accepted"];

export function OrdersFeed({ orders }: { orders: AdminOrder[] }) {
  const router = useRouter();
  const { error, busy, run } = useAdminAction();
  // одни часы на весь список: «5 минут назад» должно стареть само,
  // даже если новых заказов не приходит
  const [now, setNow] = useState(() => Date.now());

  useEffect(() => {
    const refresh = setInterval(() => router.refresh(), REFRESH_MS);
    const tick = setInterval(() => setNow(Date.now()), 30_000);
    return () => {
      clearInterval(refresh);
      clearInterval(tick);
    };
  }, [router]);

  if (orders.length === 0) {
    return (
      <p className="mt-6 rounded-2xl bg-muted px-4 py-3 text-sm text-ink-muted">
        За этот период заказов не было.
      </p>
    );
  }

  return (
    <div className="mt-4 space-y-3">
      {error !== null && (
        <p className="rounded-xl bg-muted px-3 py-2 text-sm text-danger">
          {error}
        </p>
      )}

      {orders.map((order) => (
        <OrderCard
          key={order.id}
          order={order}
          now={now}
          busy={busy}
          onRun={run}
        />
      ))}
    </div>
  );
}

function OrderCard({
  order,
  now,
  busy,
  onRun,
}: {
  order: AdminOrder;
  now: number;
  busy: boolean;
  onRun: (action: () => Promise<unknown>) => Promise<boolean>;
}) {
  const status = STATUS[order.status];
  const elapsed = formatElapsed(order.created_at, now);
  // «только что назад» — так по-русски не говорят
  const age = elapsed === "только что" ? elapsed : `${elapsed} назад`;

  return (
    <article
      className={`rounded-2xl bg-raised p-4 shadow-sm ${
        order.status === "cancelled" ? "opacity-60" : ""
      }`}
    >
      <div className="flex items-baseline gap-3">
        <p className="min-w-0 flex-1 truncate font-bold text-ink">
          {order.number}
          <span className="font-normal text-ink-faint">
            {" "}
            · {order.point_label}
          </span>
        </p>
        <span
          className={`shrink-0 rounded-full px-2.5 py-1 text-[11px] font-semibold ${status.className}`}
        >
          {status.label}
        </span>
      </div>

      <p className="mt-0.5 text-xs text-ink-faint">
        {age}
        {order.zone_name !== null && ` · ${order.zone_name}`}
      </p>

      {order.is_remote && (
        /* Не блокировка, а повод посмотреть на стол: GPS в помещении врёт */
        <p className="mt-2 rounded-xl bg-danger/10 px-3 py-2 text-xs text-danger">
          ⚠️ Телефон гостя был далеко от заведения
        </p>
      )}

      {order.cancel_reason && (
        /* Владельцу важна разница: «за столом никого» — это выброшенная еда */
        <p className="mt-2 rounded-xl bg-muted px-3 py-2 text-xs text-ink-muted">
          Отменён: {order.cancel_reason}
        </p>
      )}

      <ul className="mt-3 space-y-1">
        {order.items.map((item, i) => (
          <li key={i} className="flex justify-between gap-3 text-sm">
            <span className="min-w-0 flex-1 truncate text-ink">
              {item.name}
              {item.qty > 1 && (
                <span className="text-ink-faint"> × {item.qty}</span>
              )}
            </span>
            <span className="shrink-0 text-ink-muted tabular-nums">
              {formatPrice(item.price * item.qty)}
            </span>
          </li>
        ))}
      </ul>

      <p className="mt-2 flex justify-between border-t border-line pt-2 text-sm font-semibold text-ink">
        <span>Итого</span>
        <span className="tabular-nums">{formatPrice(order.total)}</span>
      </p>

      {order.comment && (
        <p className="mt-2 rounded-xl bg-muted px-3 py-2 text-sm text-ink-muted">
          💬 {order.comment}
        </p>
      )}

      {(order.cooked_by || order.served_by) && (
        <p className="mt-2 text-xs text-ink-faint">
          {order.cooked_by && `Готовил: ${order.cooked_by}`}
          {order.cooked_by && order.served_by && " · "}
          {order.served_by && `Отнёс: ${order.served_by}`}
        </p>
      )}

      {CANCELLABLE.includes(order.status) && (
        <button
          type="button"
          disabled={busy}
          onClick={() => {
            if (confirm(`Отменить заказ ${order.number}?`)) {
              onRun(() =>
                adminMutate(`/admin/orders/${order.id}/cancel`, {
                  method: "POST",
                }),
              );
            }
          }}
          className="mt-3 h-10 rounded-full bg-muted px-4 text-sm text-ink-muted disabled:opacity-60"
        >
          Отменить заказ
        </button>
      )}
    </article>
  );
}
