"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { fetchOrderStatus } from "@/lib/api";
import { formatElapsed, formatPrice, plural } from "@/lib/format";
import { t, withLang, type Lang } from "@/lib/i18n";
import type { OrderState } from "@/lib/types";
import { CheckIcon } from "./icons";
import { RatingCard } from "./RatingCard";

const POLL_INTERVAL_MS = 4000;

const STEPS = [
  { status: "new", title: "orderAccepted", hint: "orderAcceptedHint", icon: "📝" },
  { status: "accepted", title: "cooking", hint: "cookingHint", icon: "👨‍🍳" },
  { status: "ready", title: "ready", hint: "readyHint", icon: "🔔" },
  { status: "served", title: "served", hint: "servedHint", icon: "🍽️" },
] as const;

function waitingLabel(createdAt: string, now: number, lang: Lang): string {
  const elapsed = formatElapsed(createdAt, now);
  return elapsed === "только что"
    ? t(lang, "justNow")
    : `${t(lang, "waiting")} ${elapsed}`;
}

export function OrderStatusScreen({
  orderId,
  token,
  lang,
}: {
  orderId: number;
  token?: string;
  lang: Lang;
}) {
  const [order, setOrder] = useState<OrderState | null>(null);
  const [error, setError] = useState(false);
  const [now, setNow] = useState(() => Date.now());

  useEffect(() => {
    let cancelled = false;
    let timer: ReturnType<typeof setTimeout>;

    async function poll() {
      try {
        const fresh = await fetchOrderStatus(orderId);
        if (cancelled) return;
        setOrder(fresh);
        setError(false);
        if (fresh.status === "served" || fresh.status === "cancelled") return;
      } catch {
        if (cancelled) return;
        setError(true);
      }
      timer = setTimeout(poll, POLL_INTERVAL_MS);
    }

    poll();
    return () => {
      cancelled = true;
      clearTimeout(timer);
    };
  }, [orderId]);

  useEffect(() => {
    const id = setInterval(() => setNow(Date.now()), 30_000);
    return () => clearInterval(id);
  }, []);

  const status = order?.status ?? "new";
  const backToMenu = token ? withLang(`/m/${token}`, lang) : null;

  if (status === "cancelled") {
    return (
      <main className="flex min-h-dvh flex-col items-center justify-center gap-2 bg-surface px-8 text-center">
        <div className="flex h-20 w-20 items-center justify-center rounded-full bg-red-500/10 text-3xl">
          ❌
        </div>
        <h1 className="text-2xl font-bold text-ink">Заказ отменён</h1>
        <p className="text-ink-muted">
          Обратитесь к официанту, если это произошло по ошибке.
        </p>
        {backToMenu && (
          <Link
            href={backToMenu}
            className="mt-6 rounded-2xl bg-accent px-6 py-3.5 font-semibold text-on-accent shadow-md transition active:scale-95"
          >
            Вернуться в меню
          </Link>
        )}
      </main>
    );
  }

  const currentIndex = STEPS.findIndex((s) => s.status === status);
  const current = STEPS[currentIndex] ?? STEPS[0];
  const finished = status === "ready" || status === "served";
  const itemCount = order?.items.reduce((sum, i) => sum + i.qty, 0) ?? 0;

  return (
    <main lang={lang} className="min-h-dvh bg-surface px-5 pt-10 pb-12">
      <div className="mx-auto w-full max-w-sm">
        {/* Status Header */}
        <div className="text-center">
          <div
            className={`mx-auto flex h-24 w-24 items-center justify-center rounded-3xl text-4xl shadow-md transition-all ${
              finished
                ? "bg-emerald-500 text-white shadow-emerald-500/20"
                : "bg-raised border border-line-strong text-accent"
            }`}
          >
            {finished ? (
              <CheckIcon className="h-12 w-12 text-white motion-safe:animate-[pop_320ms_ease-out]" />
            ) : (
              <span className="animate-bounce">{current.icon}</span>
            )}
          </div>

          <h1 className="mt-5 text-2xl font-extrabold text-ink">
            {t(lang, current.title)}
          </h1>
          <p className="mt-1.5 text-sm text-ink-muted leading-relaxed">
            {t(lang, current.hint)}
          </p>

          {/* ETA Badge */}
          {status === "accepted" && (
            <div className="mt-3 inline-flex items-center gap-1.5 rounded-full bg-amber-500/10 px-3.5 py-1 text-xs font-bold text-amber-700 dark:text-amber-300">
              <span>⏱️</span>
              <span>Примерно 10-15 мин</span>
            </div>
          )}

          {order?.served_by ? (
            <p className="mt-3 inline-block rounded-full bg-muted px-4 py-1 text-xs text-ink font-medium">
              {t(lang, "servedBy")}: <b>{order.served_by}</b>
            </p>
          ) : (
            order?.cooked_by && (
              <p className="mt-3 inline-block rounded-full bg-muted px-4 py-1 text-xs text-ink font-medium">
                {t(lang, "cookedBy")}: <b>{order.cooked_by}</b>
              </p>
            )
          )}
        </div>

        {/* Visual Stepper */}
        <div className="mt-8 rounded-3xl bg-raised p-4 border border-line/60 shadow-xs">
          <div className="flex items-center justify-between gap-1 relative">
            {STEPS.map((step, i) => {
              const isDone = i <= currentIndex;
              const isCurrent = i === currentIndex;

              return (
                <div key={step.status} className="flex-1 flex flex-col items-center relative z-10">
                  <div
                    className={`flex h-10 w-10 items-center justify-center rounded-2xl text-base transition-all ${
                      isCurrent
                        ? "bg-accent text-on-accent scale-110 shadow-md ring-4 ring-accent/20"
                        : isDone
                        ? "bg-emerald-500/20 text-emerald-700 dark:text-emerald-400 font-bold"
                        : "bg-muted text-ink-faint"
                    }`}
                  >
                    {isDone && !isCurrent ? "✓" : step.icon}
                  </div>
                  <span
                    className={`mt-2 text-[10px] font-semibold text-center leading-tight ${
                      isCurrent
                        ? "text-accent font-extrabold"
                        : isDone
                        ? "text-ink"
                        : "text-ink-faint"
                    }`}
                  >
                    {t(lang, step.title)}
                  </span>
                </div>
              );
            })}
          </div>
        </div>

        {/* Order Details Card */}
        <div className="mt-6 rounded-3xl bg-raised p-5 border border-line/60 shadow-xs">
          <div className="flex items-baseline justify-between border-b border-line/60 pb-3">
            <h2 className="font-extrabold text-ink text-lg">
              {order ? order.number : `${t(lang, "order")} №${orderId}`}
            </h2>
            {order && (
              <span className="text-xs font-semibold text-ink-faint">
                {status === "served"
                  ? t(lang, "finished")
                  : waitingLabel(order.created_at, now, lang)}
              </span>
            )}
          </div>

          {order === null ? (
            <div className="mt-4 space-y-2" aria-hidden>
              <div className="h-4 w-3/4 rounded bg-muted animate-pulse" />
              <div className="h-4 w-1/2 rounded bg-muted animate-pulse" />
            </div>
          ) : (
            <>
              <ul className="mt-4 space-y-2.5">
                {order.items.map((item, i) => (
                  <li key={i} className="flex items-baseline justify-between text-[15px]">
                    <span className="min-w-0 flex-1 text-ink font-medium">
                      {item.dish_name}
                      {item.qty > 1 && (
                        <span className="text-accent font-bold"> × {item.qty}</span>
                      )}
                    </span>
                    <span className="tabular-nums text-ink font-semibold">
                      {formatPrice(item.price * item.qty)}
                    </span>
                  </li>
                ))}
              </ul>
              {order.comment && (
                <p className="mt-3 rounded-xl bg-muted px-3 py-2 text-xs text-ink-muted">
                  💬 {order.comment}
                </p>
              )}
              <div className="mt-4 flex items-baseline justify-between border-t border-line/60 pt-3">
                <span className="text-xs font-medium text-ink-faint">
                  {itemCount}{" "}
                  {lang === "ru"
                    ? plural(itemCount, "блюдо", "блюда", "блюд")
                    : t(lang, "dishes")}
                </span>
                <span className="text-xl font-extrabold text-ink">
                  {formatPrice(order.total)}
                </span>
              </div>
            </>
          )}
        </div>

        {status === "served" && (
          <>
            <p className="mt-6 rounded-2xl bg-muted px-4 py-3 text-center text-sm text-ink-muted">
              🧾 {t(lang, "billFromWaiter")}
            </p>
            <RatingCard orderId={orderId} />
          </>
        )}

        {backToMenu && (
          <Link
            href={backToMenu}
            className="mt-6 flex h-14 items-center justify-center rounded-2xl bg-accent px-6 py-3.5 font-bold text-on-accent shadow-md transition active:scale-[.98]"
          >
            {t(lang, status === "served" ? "openMenu" : "orderMore")}
          </Link>
        )}

        <p className="mt-6 text-center text-xs text-ink-faint leading-relaxed">
          {t(
            lang,
            error ? "offline" : status === "served" ? "thanks" : "autoUpdate",
          )}
        </p>
      </div>
    </main>
  );
}

