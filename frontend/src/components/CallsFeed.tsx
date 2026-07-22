"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { adminMutate } from "@/lib/api";
import { formatElapsed, plural } from "@/lib/format";
import { useAdminAction } from "@/lib/use-admin-action";
import type { AdminServiceCall } from "@/lib/types";

const REFRESH_MS = 20_000;

/** Сколько ждали: «40 с» или «3 мин» — секунды важны, тут SLA в 90 с. */
function waited(seconds: number): string {
  if (seconds < 60) return `${seconds} с`;
  const minutes = Math.floor(seconds / 60);
  return `${minutes} ${plural(minutes, "минута", "минуты", "минут")}`;
}

export function CallsFeed({ calls }: { calls: AdminServiceCall[] }) {
  const router = useRouter();
  const { error, busy, run } = useAdminAction();
  const [now, setNow] = useState(() => Date.now());

  useEffect(() => {
    const refresh = setInterval(() => router.refresh(), REFRESH_MS);
    const tick = setInterval(() => setNow(Date.now()), 30_000);
    return () => {
      clearInterval(refresh);
      clearInterval(tick);
    };
  }, [router]);

  if (calls.length === 0) {
    return (
      <p className="mt-6 rounded-2xl bg-muted px-4 py-3 text-sm text-ink-muted">
        За этот период официанта не звали.
      </p>
    );
  }

  const late = calls.filter((c) => c.escalated).length;

  return (
    <div className="mt-4 space-y-3">
      {error !== null && (
        <p className="rounded-xl bg-muted px-3 py-2 text-sm text-danger">
          {error}
        </p>
      )}

      {late > 0 && (
        <p className="rounded-2xl bg-danger/10 px-4 py-3 text-sm text-danger">
          Просрочено вызовов: {late} из {calls.length}. К этим столам не подошли
          вовремя.
        </p>
      )}

      {calls.map((call) => (
        <article
          key={call.id}
          className={`rounded-2xl p-4 shadow-sm ${
            call.resolved_at === null
              ? "bg-danger/10"
              : call.escalated
                ? "bg-raised ring-1 ring-danger/30"
                : "bg-raised"
          }`}
        >
          <div className="flex items-baseline gap-3">
            <p className="min-w-0 flex-1 truncate font-bold text-ink">
              {call.point_label}
              <span className="font-normal text-ink-faint">
                {" "}
                · {call.zone_name}
              </span>
            </p>
            <span
              className={`shrink-0 rounded-full px-2.5 py-1 text-[11px] font-semibold ${
                call.resolved_at === null
                  ? "bg-danger/15 text-danger"
                  : "bg-muted text-ink-muted"
              }`}
            >
              {call.resolved_at === null ? "открыт" : "закрыт"}
            </span>
          </div>

          <p className="mt-0.5 text-xs text-ink-faint">
            {formatElapsed(call.created_at, now)} назад · ждали{" "}
            {waited(call.waiting_seconds)}
            {call.escalated && " · просрочен"}
          </p>

          {call.comment && (
            <p className="mt-2 rounded-xl bg-muted px-3 py-2 text-sm text-ink-muted">
              💬 {call.comment}
            </p>
          )}

          {call.taken_by !== null && (
            <p className="mt-2 text-xs text-ink-faint">Подошёл: {call.taken_by}</p>
          )}

          {call.resolved_at === null && (
            <button
              type="button"
              disabled={busy}
              onClick={() =>
                run(() =>
                  adminMutate(`/admin/calls/${call.id}/resolve`, {
                    method: "POST",
                  }),
                )
              }
              className="mt-3 h-10 rounded-full bg-muted px-4 text-sm text-ink-muted disabled:opacity-60"
            >
              Закрыть вызов
            </button>
          )}
        </article>
      ))}
    </div>
  );
}
