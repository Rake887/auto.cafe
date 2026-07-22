"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

const MIN_LENGTH = 8;

/** Первичная настройка: создаёт владельца и сразу пускает в кабинет. */
export function SetupForm() {
  const router = useRouter();
  const [login, setLogin] = useState("");
  const [fullName, setFullName] = useState("");
  const [password, setPassword] = useState("");
  const [repeat, setRepeat] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function submit() {
    setError(null);
    if (password !== repeat) {
      setError("Пароли не совпадают");
      return;
    }
    if (password.length < MIN_LENGTH) {
      setError(`Пароль короче ${MIN_LENGTH} символов`);
      return;
    }

    setBusy(true);
    try {
      const res = await fetch("/api/admin/setup", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          login: login.trim(),
          password,
          full_name: fullName.trim() || login.trim(),
        }),
      });
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        setError(body.detail ?? "Не удалось создать владельца");
        setBusy(false);
        return;
      }
      router.push("/admin");
      router.refresh();
    } catch {
      setError("Нет связи с сервером");
      setBusy(false);
    }
  }

  return (
    <form
      onSubmit={(e) => {
        e.preventDefault();
        submit();
      }}
      className="mt-6 space-y-3"
    >
      <label className="block">
        <span className="text-sm text-ink-muted">Логин</span>
        <input
          value={login}
          onChange={(e) => setLogin(e.target.value)}
          autoComplete="username"
          required
          className="mt-1 h-12 w-full rounded-xl border border-line bg-raised px-3 text-[15px] text-ink focus:border-accent focus:outline-none"
        />
      </label>

      <label className="block">
        <span className="text-sm text-ink-muted">Имя владельца</span>
        <input
          value={fullName}
          onChange={(e) => setFullName(e.target.value)}
          placeholder="Как показывать в кабинете"
          className="mt-1 h-12 w-full rounded-xl border border-line bg-raised px-3 text-[15px] text-ink focus:border-accent focus:outline-none"
        />
      </label>

      <label className="block">
        <span className="text-sm text-ink-muted">Пароль</span>
        <input
          type="password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          autoComplete="new-password"
          required
          className="mt-1 h-12 w-full rounded-xl border border-line bg-raised px-3 text-[15px] text-ink focus:border-accent focus:outline-none"
        />
      </label>

      <label className="block">
        <span className="text-sm text-ink-muted">Пароль ещё раз</span>
        <input
          type="password"
          value={repeat}
          onChange={(e) => setRepeat(e.target.value)}
          autoComplete="new-password"
          required
          className="mt-1 h-12 w-full rounded-xl border border-line bg-raised px-3 text-[15px] text-ink focus:border-accent focus:outline-none"
        />
      </label>

      {error !== null && (
        <p className="rounded-xl bg-muted px-3 py-2 text-sm text-danger">
          {error}
        </p>
      )}

      <button
        type="submit"
        disabled={busy}
        className="h-12 w-full rounded-xl bg-accent font-semibold text-on-accent disabled:opacity-60"
      >
        {busy ? "Создаём…" : "Создать и войти"}
      </button>
    </form>
  );
}
