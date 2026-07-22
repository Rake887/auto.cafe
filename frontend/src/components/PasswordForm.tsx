"use client";

import { useState } from "react";
import { adminMutate } from "@/lib/api";

const MIN_LENGTH = 8;

export function PasswordForm() {
  const [current, setCurrent] = useState("");
  const [next, setNext] = useState("");
  const [repeat, setRepeat] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState(false);

  async function submit() {
    setError(null);
    setDone(false);
    if (next !== repeat) {
      setError("Новый пароль и повтор не совпадают");
      return;
    }
    if (next.length < MIN_LENGTH) {
      setError(`Пароль короче ${MIN_LENGTH} символов`);
      return;
    }

    setBusy(true);
    try {
      await adminMutate("/admin/password", {
        method: "POST",
        body: JSON.stringify({
          current_password: current,
          new_password: next,
        }),
      });
      setCurrent("");
      setNext("");
      setRepeat("");
      setDone(true);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Не удалось сменить пароль");
    }
    setBusy(false);
  }

  return (
    <form
      onSubmit={(e) => {
        e.preventDefault();
        submit();
      }}
      className="space-y-2 rounded-2xl border border-line bg-raised p-4"
    >
      <h2 className="font-bold text-ink">Сменить пароль</h2>

      <Field
        label="Текущий пароль"
        value={current}
        onChange={setCurrent}
        autoComplete="current-password"
      />
      <Field
        label="Новый пароль"
        value={next}
        onChange={setNext}
        autoComplete="new-password"
      />
      <Field
        label="Новый пароль ещё раз"
        value={repeat}
        onChange={setRepeat}
        autoComplete="new-password"
      />

      {error !== null && (
        <p className="rounded-xl bg-muted px-3 py-2 text-sm text-danger">
          {error}
        </p>
      )}
      {done && (
        <p className="rounded-xl bg-muted px-3 py-2 text-sm text-ink-muted">
          Пароль изменён. Остальные устройства выкинуты из кабинета.
        </p>
      )}

      <button
        type="submit"
        disabled={busy}
        className="h-11 w-full rounded-xl bg-accent font-semibold text-on-accent disabled:opacity-60"
      >
        {busy ? "Сохраняем…" : "Сохранить"}
      </button>
    </form>
  );
}

function Field({
  label,
  value,
  onChange,
  autoComplete,
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
  autoComplete: string;
}) {
  return (
    <label className="block">
      <span className="text-sm text-ink-muted">{label}</span>
      <input
        type="password"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        autoComplete={autoComplete}
        required
        className="mt-1 h-11 w-full rounded-xl border border-line bg-surface px-3 text-[15px] text-ink focus:border-accent focus:outline-none"
      />
    </label>
  );
}
