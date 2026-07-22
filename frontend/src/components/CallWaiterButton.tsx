"use client";

import { useEffect, useState } from "react";
import { callWaiter } from "@/lib/api";
import { ApiError } from "@/lib/api-error";
import { t, type Lang, type MessageKey } from "@/lib/i18n";
import { BellIcon, CheckIcon, CloseIcon } from "./icons";

const COOLDOWN_SEC = 60;

// Быстрые пожелания. Ключи — из словаря i18n (см. lib/i18n.ts).
const CHIP_KEYS: MessageKey[] = [
  "chipBill",
  "chipCutlery",
  "chipNapkins",
  "chipWater",
  "chipClear",
];

type Phase = "form" | "sending" | "sent" | "error";

/**
 * Вызов официанта со шторкой: гость отмечает быстрые пожелания (счёт, приборы,
 * салфетки…) и/или пишет комментарий — всё уходит в чат заведения одним
 * сообщением. После отправки кнопка на минуту гаснет (антиспам, как на бэкенде).
 */
export function CallWaiterButton({ token, lang }: { token: string; lang: Lang }) {
  const [open, setOpen] = useState(false);
  const [phase, setPhase] = useState<Phase>("form");
  const [selected, setSelected] = useState<Set<MessageKey>>(new Set());
  const [comment, setComment] = useState("");
  const [left, setLeft] = useState(0);

  // Отсчёт паузы: «официант идёт» выводится из left, отдельного флага нет.
  useEffect(() => {
    if (left <= 0) return;
    const id = setTimeout(() => setLeft((s) => s - 1), 1000);
    return () => clearTimeout(id);
  }, [left]);

  // Открытая шторка модальна: Escape закрывает, фон не прокручивается.
  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") setOpen(false);
    };
    document.addEventListener("keydown", onKey);
    const previous = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.removeEventListener("keydown", onKey);
      document.body.style.overflow = previous;
    };
  }, [open]);

  function openSheet() {
    setPhase("form");
    setSelected(new Set());
    setComment("");
    setOpen(true);
  }

  function toggle(key: MessageKey) {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(key)) {
        next.delete(key);
      } else {
        next.add(key);
      }
      return next;
    });
  }

  async function send() {
    const chips = CHIP_KEYS.filter((k) => selected.has(k)).map((k) => t(lang, k));
    const message = [chips.join(", "), comment.trim()].filter(Boolean).join(". ");
    setPhase("sending");
    try {
      await callWaiter(token, message || undefined);
      setPhase("sent");
      setLeft(COOLDOWN_SEC);
      setTimeout(() => setOpen(false), 2600);
    } catch (e) {
      // 429 — вызов уже принят, для гостя это успех, а не ошибка
      if (e instanceof ApiError && e.status === 429) {
        setPhase("sent");
        setLeft(COOLDOWN_SEC);
        setTimeout(() => setOpen(false), 2600);
        return;
      }
      setPhase("error");
    }
  }

  const called = left > 0;

  return (
    <>
      <button
        type="button"
        onClick={openSheet}
        disabled={called}
        aria-live="polite"
        className="inline-flex h-11 shrink-0 items-center gap-1.5 rounded-full border border-line-strong px-4 text-sm whitespace-nowrap text-ink-muted transition active:bg-muted disabled:opacity-70"
      >
        <BellIcon className="h-4 w-4" />
        {called
          ? `${t(lang, "waiterComing")} · ${left}`
          : t(lang, "callWaiter")}
      </button>

      {open && (
        <>
          <div
            onClick={() => setOpen(false)}
            className="fixed inset-0 z-40 bg-black/30 motion-safe:animate-[rise_200ms_ease-out]"
            aria-hidden
          />
          <div
            role="dialog"
            aria-label={t(lang, "callWaiter")}
            className="fixed inset-x-0 bottom-0 z-50 rounded-t-3xl bg-surface pb-[max(1.5rem,env(safe-area-inset-bottom))] shadow-[0_-8px_32px_rgba(42,33,27,0.18)] motion-safe:animate-[slide-up_260ms_cubic-bezier(.22,1,.36,1)]"
          >
            <div className="flex justify-center pt-2.5" aria-hidden>
              <span className="h-1 w-10 rounded-full bg-line-strong" />
            </div>

            {phase !== "sent" ? (
              <div>
                <div className="flex items-center justify-between px-6 pt-2 pb-1">
                  <h2 className="text-2xl font-bold text-ink">
                    {t(lang, "callWaiter")}
                  </h2>
                  <button
                    type="button"
                    onClick={() => setOpen(false)}
                    aria-label={t(lang, "closeCart")}
                    className="flex h-10 w-10 items-center justify-center rounded-full text-ink-muted active:bg-muted"
                  >
                    <CloseIcon className="h-5 w-5" />
                  </button>
                </div>
                <p className="px-6 text-sm text-ink-faint">
                  {t(lang, "waiterHint")}
                </p>

                <div className="flex flex-wrap gap-2 px-6 pt-4">
                  {CHIP_KEYS.map((key) => {
                    const on = selected.has(key);
                    return (
                      <button
                        key={key}
                        type="button"
                        onClick={() => toggle(key)}
                        aria-pressed={on}
                        className={`rounded-full px-3.5 py-2 text-sm font-semibold transition ${
                          on
                            ? "border border-transparent bg-accent text-on-accent"
                            : "border border-line-strong bg-raised text-ink-muted"
                        }`}
                      >
                        {t(lang, key)}
                      </button>
                    );
                  })}
                </div>

                <div className="px-6 pt-4">
                  <textarea
                    value={comment}
                    onChange={(e) => setComment(e.target.value.slice(0, 200))}
                    rows={2}
                    placeholder={t(lang, "waiterCommentPlaceholder")}
                    className="w-full resize-none rounded-2xl border border-line-strong bg-raised px-3.5 py-3 text-[15px] text-ink placeholder:text-ink-faint focus:border-accent focus:outline-none"
                  />
                </div>

                <div className="px-6 pt-4">
                  {phase === "error" && (
                    <p className="mb-3 rounded-xl bg-muted px-3 py-2 text-sm text-danger">
                      {t(lang, "callFailed")}
                    </p>
                  )}
                  <button
                    type="button"
                    onClick={send}
                    disabled={phase === "sending"}
                    className="h-14 w-full rounded-2xl bg-accent text-[17px] font-semibold text-on-accent transition active:scale-[.98] active:bg-accent-strong disabled:opacity-70"
                  >
                    {phase === "sending"
                      ? t(lang, "calling")
                      : t(lang, "callWaiter")}
                  </button>
                </div>
              </div>
            ) : (
              <div className="px-6 pt-3 pb-2 text-center motion-safe:animate-[rise_300ms_ease-out]">
                <div className="mx-auto flex h-18 w-18 items-center justify-center rounded-full bg-success text-white">
                  <CheckIcon className="h-9 w-9 motion-safe:animate-[pop_340ms_ease-out]" />
                </div>
                <h2 className="mt-4 text-2xl font-bold text-ink">
                  {t(lang, "waiterSentTitle")}
                </h2>
                <p className="mt-1.5 text-sm text-ink-muted">
                  {t(lang, "waiterSentHint")}
                </p>
                <button
                  type="button"
                  onClick={() => setOpen(false)}
                  className="mt-5 h-12 w-full rounded-2xl border border-line-strong bg-raised font-semibold text-ink active:bg-muted"
                >
                  {t(lang, "waiterOk")}
                </button>
              </div>
            )}
          </div>
        </>
      )}
    </>
  );
}
