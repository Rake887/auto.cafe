import { redirect } from "next/navigation";
import { LoginForm } from "@/components/LoginForm";
import { fetchSetupState } from "@/lib/api";

export const dynamic = "force-dynamic";

export default async function LoginPage() {
  // На чистой базе входить некому — сразу отправляем создавать владельца
  const state = await fetchSetupState();
  if (state?.needs_setup) redirect("/admin/setup");

  return (
    <main className="relative mx-auto flex min-h-dvh w-full max-w-sm flex-col justify-center px-6 py-12">
      {/* Decorative gradient blob */}
      <div className="pointer-events-none absolute inset-0 overflow-hidden">
        <div
          className="absolute -top-32 -right-32 h-80 w-80 rounded-full opacity-20 blur-3xl"
          style={{ background: "linear-gradient(135deg, var(--color-accent), #6366f1)" }}
        />
        <div
          className="absolute -bottom-20 -left-20 h-60 w-60 rounded-full opacity-15 blur-3xl"
          style={{ background: "linear-gradient(135deg, #f59e0b, var(--color-accent))" }}
        />
      </div>

      <div className="relative">
        {/* Logo / Brand */}
        <div className="flex items-center gap-3">
          <div className="flex h-11 w-11 items-center justify-center rounded-2xl bg-accent text-xl shadow-md">
            ☕
          </div>
          <div>
            <p className="text-[10px] font-extrabold tracking-[0.18em] text-accent uppercase">
              Auto.Cafe
            </p>
            <p className="text-xs text-ink-faint">Кабинет заведения</p>
          </div>
        </div>

        <h1 className="mt-6 text-3xl font-extrabold text-ink">
          Добро пожаловать
        </h1>
        <p className="mt-2 text-sm leading-relaxed text-ink-muted">
          Войдите, чтобы управлять меню, видеть заказы и аналитику вашего
          заведения в реальном времени.
        </p>

        <LoginForm />

        <p className="mt-6 text-center text-[11px] text-ink-faint">
          Нет аккаунта?{" "}
          <span className="font-semibold text-accent">Обратитесь к администратору</span>
        </p>
      </div>
    </main>
  );
}
