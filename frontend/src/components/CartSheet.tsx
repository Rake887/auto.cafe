"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { createOrder } from "@/lib/api";
import { formatPrice, plural } from "@/lib/format";
import { t, withLang, type Lang } from "@/lib/i18n";
import { useCart } from "./cart-context";
import { CloseIcon, MinusIcon, PlusIcon } from "./icons";

interface Props {
  open: boolean;
  onClose: () => void;
  pointToken: string;
  lang: Lang;
  /** заведение задало координаты — есть смысл прикладывать геопозицию */
  geoEnabled: boolean;
}

const COMMENT_MAX = 300;

export function CartSheet({
  open,
  onClose,
  pointToken,
  lang,
  geoEnabled,
}: Props) {
  const { lines, total, count, add, remove, getRequestId } = useCart();
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [comment, setComment] = useState("");
  const router = useRouter();

  // Открытая шторка — модальная: Escape закрывает, фон под ней не прокручивается
  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    document.addEventListener("keydown", onKey);
    const previous = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.removeEventListener("keydown", onKey);
      document.body.style.overflow = previous;
    };
  }, [open, onClose]);

  /** Координаты гостя, если браузер отдаст их быстро.
   *
   *  Заказ они не блокируют: часть гостей всегда откажет в доступе, а в зале
   *  с толстыми стенами GPS может не определиться вовсе. Ждать дольше пары
   *  секунд ради необязательной метки нельзя — это задержка оформления.
   */
  async function guestPosition(): Promise<{ lat?: number; lon?: number }> {
    // заведение не задало координаты — позиция ни на что не влияет
    if (!geoEnabled) return {};
    if (typeof navigator === "undefined" || !navigator.geolocation) return {};
    return new Promise((resolve) => {
      navigator.geolocation.getCurrentPosition(
        (p) => resolve({ lat: p.coords.latitude, lon: p.coords.longitude }),
        () => resolve({}),
        { timeout: 2000, maximumAge: 300_000 },
      );
    });
  }

  async function submit() {
    setSubmitting(true);
    setError(null);
    try {
      const position = await guestPosition();
      const order = await createOrder({
        point_token: pointToken,
        // тот же id при повторе после ошибки сети — бэкенд не создаст дубль
        client_request_id: getRequestId(),
        items: lines.map((l) => ({ dish_id: l.dish.id, qty: l.qty })),
        comment: comment.trim() || null,
        ...position,
      });
      // токен стола тащим в URL: с экрана статуса можно вернуться в своё меню
      router.push(
        withLang(`/order/${order.order_id}?t=${encodeURIComponent(pointToken)}`, lang),
      );
    } catch (e) {
      setError(
        e instanceof Error ? e.message : "Не удалось отправить заказ",
      );
      setSubmitting(false);
    }
  }

  return (
    <>
      <div
        onClick={onClose}
        className={`fixed inset-0 z-40 bg-black/30 transition-opacity ${
          open ? "opacity-100" : "pointer-events-none opacity-0"
        }`}
        aria-hidden
      />
      <div
        role="dialog"
        aria-label="Корзина"
        aria-hidden={!open}
        className={`fixed inset-x-0 bottom-0 z-50 max-h-[80vh] overflow-y-auto rounded-t-3xl bg-raised pb-[env(safe-area-inset-bottom)] shadow-[0_-8px_32px_rgba(42,33,27,0.18)] transition-transform duration-250 ${
          open ? "translate-y-0" : "translate-y-full"
        }`}
      >
        {/* ручка-хват: привычный признак того, что шторку можно закрыть */}
        <div className="flex justify-center pt-2.5" aria-hidden>
          <span className="h-1 w-10 rounded-full bg-line" />
        </div>

        <div className="sticky top-0 flex items-center justify-between bg-raised px-5 pt-2 pb-2">
          <h2 className="text-lg font-bold text-ink">
            {t(lang, "yourOrder")}
            {count > 0 && (
              <span className="ml-2 text-sm font-medium text-ink-faint">
                {count}{" "}
                {lang === "ru"
                  ? plural(count, "блюдо", "блюда", "блюд")
                  : t(lang, "dishes")}
              </span>
            )}
          </h2>
          <button
            type="button"
            onClick={onClose}
            aria-label={t(lang, "closeCart")}
            className="flex h-11 w-11 items-center justify-center rounded-full text-ink-muted active:bg-muted"
          >
            <CloseIcon className="h-5 w-5" />
          </button>
        </div>

        {lines.length === 0 ? (
          <p className="px-5 py-10 text-center text-ink-faint">
            {t(lang, "emptyCart")}
          </p>
        ) : (
          <ul className="divide-y divide-line px-5">
            {lines.map((line) => (
              <li key={line.dish.id} className="flex items-center gap-3 py-3">
                <div className="min-w-0 flex-1">
                  <p className="text-[15px] font-medium text-ink">
                    {line.dish.name}
                  </p>
                  <p className="mt-0.5 text-sm text-ink-muted">
                    {formatPrice(line.dish.price * line.qty)}
                    {line.qty > 1 && (
                      <span className="text-ink-faint">
                        {" "}
                        · {formatPrice(line.dish.price)} {t(lang, "perItem")}
                      </span>
                    )}
                  </p>
                </div>
                <div className="flex h-11 items-center gap-1 rounded-full border border-line px-1">
                  <button
                    type="button"
                    onClick={() => remove(line.dish.id)}
                    aria-label={`Убрать «${line.dish.name}»`}
                    className="flex h-9 w-9 items-center justify-center rounded-full text-ink-muted active:bg-muted"
                  >
                    <MinusIcon className="h-4 w-4" />
                  </button>
                  <span className="min-w-5 text-center font-semibold tabular-nums text-ink">
                    {line.qty}
                  </span>
                  <button
                    type="button"
                    onClick={() => add(line.dish)}
                    aria-label={`Добавить «${line.dish.name}»`}
                    className="flex h-9 w-9 items-center justify-center rounded-full text-accent active:bg-muted"
                  >
                    <PlusIcon className="h-4 w-4" />
                  </button>
                </div>
              </li>
            ))}
          </ul>
        )}

        {lines.length > 0 && (
          <div className="px-5 pt-4">
            <label
              htmlFor="order-comment"
              className="text-sm font-medium text-ink"
            >
              {t(lang, "wish")}
            </label>
            <textarea
              id="order-comment"
              value={comment}
              onChange={(e) => setComment(e.target.value.slice(0, COMMENT_MAX))}
              rows={2}
              placeholder={t(lang, "wishPlaceholder")}
              className="mt-1.5 w-full resize-none rounded-2xl border border-line bg-surface px-3 py-2.5 text-[15px] text-ink placeholder:text-ink-faint focus:border-accent focus:outline-none"
            />
            {comment.length > COMMENT_MAX - 50 && (
              <p className="mt-1 text-right text-xs text-ink-faint">
                {COMMENT_MAX - comment.length}
              </p>
            )}
          </div>
        )}

        <div className="sticky bottom-0 border-t border-line bg-raised px-5 py-4">
          {error !== null && (
            <p className="mb-3 rounded-xl bg-muted px-3 py-2 text-sm text-danger">
              {error} {t(lang, "sendError")}
            </p>
          )}
          <div className="mb-3 flex items-baseline justify-between">
            <span className="text-ink-muted">{t(lang, "total")}</span>
            <span className="text-xl font-bold text-ink">
              {formatPrice(total)}
            </span>
          </div>
          <button
            type="button"
            onClick={submit}
            disabled={lines.length === 0 || submitting}
            className="h-13 w-full rounded-2xl bg-accent py-3.5 text-[17px] font-semibold text-on-accent transition active:bg-accent-strong disabled:bg-line disabled:text-ink-faint"
          >
            {submitting
              ? t(lang, "sending")
              : error !== null
                ? t(lang, "retry")
                : t(lang, "placeOrder")}
          </button>
        </div>
      </div>
    </>
  );
}
