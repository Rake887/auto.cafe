"use client";

import { useState } from "react";
import { adminMutate } from "@/lib/api";
import { formatElapsed, formatPrice } from "@/lib/format";
import { useAdminAction } from "@/lib/use-admin-action";
import type { AdminReview } from "@/lib/types";

/** Ниже этого — жалоба, её нужно разобрать. */
const GOOD_RATING = 4;

export function ReviewsFeed({ reviews }: { reviews: AdminReview[] }) {
  const { error, busy, run } = useAdminAction();
  const [now] = useState(() => Date.now());

  if (reviews.length === 0) {
    return (
      <p className="mt-6 rounded-2xl bg-muted px-4 py-3 text-sm text-ink-muted">
        За этот период оценок не было. Гость видит звёзды на экране заказа
        после того, как официант нажал «Обслуживаю».
      </p>
    );
  }

  const average =
    reviews.reduce((sum, r) => sum + r.rating, 0) / reviews.length;
  const pending = reviews.filter(
    (r) => r.rating < GOOD_RATING && r.resolved_at === null,
  ).length;

  return (
    <div className="mt-4 space-y-3">
      {error !== null && (
        <p className="rounded-xl bg-muted px-3 py-2 text-sm text-danger">
          {error}
        </p>
      )}

      <div className="flex items-baseline justify-between rounded-2xl bg-raised px-4 py-3 shadow-sm">
        <span className="text-sm text-ink-muted">
          Средняя оценка за период
        </span>
        <span className="text-xl font-extrabold text-ink tabular-nums">
          {average.toFixed(1)}
          <span className="text-sm font-normal text-ink-faint">
            {" "}
            из 5 · {reviews.length}
          </span>
        </span>
      </div>

      {pending > 0 && (
        <p className="rounded-2xl bg-danger/10 px-4 py-3 text-sm text-danger">
          Не разобрано жалоб: {pending}. Отметьте разобранные — они уйдут из
          сводки на главной.
        </p>
      )}

      {reviews.map((review) => (
        <article
          key={review.id}
          className={`rounded-2xl p-4 shadow-sm ${
            review.rating < GOOD_RATING && review.resolved_at === null
              ? "bg-danger/10"
              : "bg-raised"
          }`}
        >
          <div className="flex items-baseline gap-3">
            <p className="shrink-0 text-lg" aria-label={`${review.rating} из 5`}>
              {"⭐".repeat(review.rating)}
            </p>
            <p className="min-w-0 flex-1 truncate text-right text-xs text-ink-faint">
              {formatElapsed(review.created_at, now)} назад
            </p>
          </div>

          <p className="mt-1 text-xs text-ink-faint">
            {review.order_number} · {review.point_label} ·{" "}
            {formatPrice(review.order_total)}
          </p>

          {review.comment && (
            <p className="mt-2 rounded-xl bg-surface px-3 py-2 text-sm text-ink">
              {review.comment}
            </p>
          )}

          {review.rating < GOOD_RATING &&
            (review.resolved_at === null ? (
              <button
                type="button"
                disabled={busy}
                onClick={() =>
                  run(() =>
                    adminMutate(`/admin/reviews/${review.id}/resolve`, {
                      method: "POST",
                    }),
                  )
                }
                className="mt-3 h-10 rounded-full bg-muted px-4 text-sm text-ink disabled:opacity-60"
              >
                Разобрался
              </button>
            ) : (
              <p className="mt-2 text-xs text-ink-faint">✓ Разобрано</p>
            ))}
        </article>
      ))}
    </div>
  );
}
