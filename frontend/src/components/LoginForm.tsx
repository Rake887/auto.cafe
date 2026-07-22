"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

/** Кнопка демо-входа под явным флагом сборки.
 *
 *  Она логинит демо-администратора известной парой логин/пароль. На стенде
 *  это удобно, на боевом домене — открытая дверь в кабинет владельца: меню,
 *  выручка, персонал. Достаточно, чтобы кто-то однажды прогнал сидинг.
 *  Поэтому по умолчанию выключена и включается только на демо-сборке.
 */
const DEMO_LOGIN = process.env.NEXT_PUBLIC_DEMO_LOGIN === "1";

export function LoginForm() {
  const [login, setLogin] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const router = useRouter();

  async function performLogin(loginVal: string, passwordVal: string) {
    setBusy(true);
    setError(null);
    try {
      const res = await fetch("/api/admin/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ login: loginVal, password: passwordVal }),
      });
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        setError(body.detail ?? "Не удалось войти");
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

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    await performLogin(login, password);
  }

  return (
    <div className="mt-6 space-y-5">
      {DEMO_LOGIN && (
        <>
      <button
        type="button"
        disabled={busy}
        onClick={() => performLogin("admin", "adminpassword123")}
        className="group relative w-full overflow-hidden rounded-2xl bg-gradient-to-r from-accent to-[#6366f1] p-[1px] shadow-lg transition active:scale-[0.98]"
      >
        <div className="flex items-center justify-center gap-2 rounded-[15px] bg-surface/90 py-3 backdrop-blur-sm transition group-hover:bg-surface/70 dark:bg-ink/50">
          <span className="text-lg">🚀</span>
          <span className="text-sm font-bold text-ink">Демо-вход в 1 клик</span>
        </div>
      </button>

      <div className="flex items-center gap-3">
        <div className="h-px flex-1 bg-line" />
        <span className="text-[10px] font-bold uppercase tracking-wider text-ink-faint">
          или свой аккаунт
        </span>
        <div className="h-px flex-1 bg-line" />
      </div>
        </>
      )}

      {/* Login Form */}
      <form onSubmit={submit} className="space-y-4">
        <div>
          <label htmlFor="login" className="text-xs font-bold text-ink-muted">
            Логин
          </label>
          <input
            id="login"
            value={login}
            onChange={(e) => setLogin(e.target.value)}
            autoComplete="username"
            autoCapitalize="none"
            placeholder="admin"
            required
            className="mt-1.5 h-12 w-full rounded-2xl border border-line bg-raised px-4 text-sm font-medium text-ink placeholder:text-ink-faint/40 focus:border-accent focus:ring-2 focus:ring-accent/20 focus:outline-none transition"
          />
        </div>

        <div>
          <label htmlFor="password" className="text-xs font-bold text-ink-muted">
            Пароль
          </label>
          <div className="relative mt-1.5">
            <input
              id="password"
              type={showPassword ? "text" : "password"}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              autoComplete="current-password"
              placeholder="••••••••"
              required
              className="h-12 w-full rounded-2xl border border-line bg-raised pl-4 pr-12 text-sm font-medium text-ink placeholder:text-ink-faint/40 focus:border-accent focus:ring-2 focus:ring-accent/20 focus:outline-none transition"
            />
            <button
              type="button"
              onClick={() => setShowPassword(!showPassword)}
              className="absolute right-3 top-1/2 -translate-y-1/2 rounded-lg p-1 text-ink-faint hover:text-ink hover:bg-muted transition"
              aria-label={showPassword ? "Скрыть пароль" : "Показать пароль"}
            >
              {showPassword ? (
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19m-6.72-1.07a3 3 0 1 1-4.24-4.24" />
                  <line x1="1" y1="1" x2="23" y2="23" />
                </svg>
              ) : (
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z" />
                  <circle cx="12" cy="12" r="3" />
                </svg>
              )}
            </button>
          </div>
        </div>

        {error !== null && (
          <div className="flex items-center gap-2 rounded-xl bg-red-500/10 px-4 py-3 text-sm text-red-600 dark:text-red-400">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="shrink-0">
              <circle cx="12" cy="12" r="10" />
              <line x1="12" y1="8" x2="12" y2="12" />
              <line x1="12" y1="16" x2="12.01" y2="16" />
            </svg>
            <span className="font-medium">{error}</span>
          </div>
        )}

        <button
          type="submit"
          disabled={busy}
          className="h-12 w-full rounded-2xl bg-ink text-sm font-bold text-surface transition active:scale-[0.98] disabled:opacity-40 dark:bg-raised dark:text-ink dark:border dark:border-line-strong shadow-md hover:shadow-lg"
        >
          {busy ? (
            <span className="flex items-center justify-center gap-2">
              <svg className="h-4 w-4 animate-spin" viewBox="0 0 24 24" fill="none">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
              </svg>
              Проверяем…
            </span>
          ) : (
            "Войти в кабинет"
          )}
        </button>
      </form>
    </div>
  );
}
