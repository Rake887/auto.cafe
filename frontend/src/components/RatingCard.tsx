"use client";

import { useState } from "react";
import { submitReview } from "@/lib/api";

/** Ниже этого гостя не зовём на публичные карты, а спрашиваем, что не так. */
const GOOD_RATING = 4;

type Stage = "ask" | "complaint" | "done";

/** Оценка гостя после подачи заказа.
 *
 *  Развилка по оценке не косметическая: довольного гостя ведём на публичные
 *  карты, а недовольного — во внутреннюю форму, и его жалоба сразу уходит в
 *  чат заведения. Пока человек за столом, проблему ещё можно решить.
 */
export function RatingCard({ orderId }: { orderId: number }) {
  const [stage, setStage] = useState<Stage>("ask");
  const [rating, setRating] = useState<number | null>(null);
  const [comment, setComment] = useState("");
  const [reviewUrl, setReviewUrl] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function send(stars: number, text?: string) {
    setBusy(true);
    setError(null);
    try {
      const result = await submitReview(orderId, stars, text);
      setReviewUrl(result.review_url);
      setStage("done");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Не удалось отправить оценку");
      // возвращаем к звёздам: иначе гость застрянет на форме без выхода
      setStage("ask");
    }
    setBusy(false);
  }

  function pick(stars: number) {
    setRating(stars);
    if (stars >= GOOD_RATING) {
      send(stars);
    } else {
      // низкую оценку не отправляем сразу: сначала спрашиваем, что не так
      setStage("complaint");
    }
  }

  return (
    <div className="mt-6 rounded-3xl border border-line/60 bg-raised p-5 text-center shadow-xs">
      <h3 className="text-sm font-bold text-ink">Оцените обслуживание</h3>

      {stage === "ask" && (
        <>
          <p className="mt-0.5 text-xs text-ink-faint">
            Ваш отзыв поможет сделать сервис лучше
          </p>
          <div className="mt-3 flex justify-center gap-2">
            {[1, 2, 3, 4, 5].map((star) => (
              <button
                key={star}
                type="button"
                disabled={busy}
                aria-label={`Оценка ${star} из 5`}
                onClick={() => pick(star)}
                className={`text-2xl transition-transform hover:scale-125 active:scale-95 disabled:opacity-50 ${
                  rating !== null && rating >= star ? "opacity-100" : "opacity-40"
                }`}
              >
                ⭐
              </button>
            ))}
          </div>
        </>
      )}

      {stage === "complaint" && (
        <form
          onSubmit={(e) => {
            e.preventDefault();
            if (rating !== null) send(rating, comment.trim() || undefined);
          }}
          className="mt-3"
        >
          <p className="text-xs text-ink-muted">
            Жаль, что не понравилось. Что пошло не так? Управляющий увидит это
            сразу.
          </p>
          <textarea
            value={comment}
            onChange={(e) => setComment(e.target.value.slice(0, 1000))}
            rows={3}
            autoFocus
            aria-label="Что пошло не так"
            className="mt-2 w-full resize-none rounded-xl border border-line bg-surface px-3 py-2 text-left text-[15px] text-ink focus:border-accent focus:outline-none"
          />
          <button
            type="submit"
            disabled={busy}
            className="mt-2 h-11 w-full rounded-xl bg-accent font-semibold text-on-accent disabled:opacity-60"
          >
            {busy ? "Отправляем…" : "Отправить"}
          </button>
        </form>
      )}

      {stage === "done" && (
        <>
          <p className="mt-3 text-xs font-bold text-emerald-600 dark:text-emerald-400">
            ❤️ Спасибо за вашу оценку!
          </p>
          {reviewUrl !== null && (
            <>
              <p className="mt-2 text-xs text-ink-muted">
                Расскажете о нас другим?
              </p>
              <a
                href={reviewUrl}
                target="_blank"
                rel="noopener noreferrer"
                className="mt-2 flex h-11 items-center justify-center rounded-xl bg-muted font-medium text-ink"
              >
                Оставить отзыв
              </a>
            </>
          )}
        </>
      )}

      {error !== null && (
        <p className="mt-2 text-xs text-danger">{error}</p>
      )}
    </div>
  );
}
