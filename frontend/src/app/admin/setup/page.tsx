import { redirect } from "next/navigation";
import { fetchSetupState } from "@/lib/api";
import { SetupForm } from "@/components/SetupForm";

export const dynamic = "force-dynamic";

export default async function SetupPage() {
  // Владелец уже есть — форму показывать нельзя, иначе доступ заведёт любой
  const state = await fetchSetupState();
  if (state === null || !state.needs_setup) redirect("/admin/login");

  return (
    <main className="mx-auto flex min-h-dvh w-full max-w-sm flex-col justify-center px-6 py-12">
      <div className="flex items-center gap-3">
        <div className="flex h-11 w-11 items-center justify-center rounded-2xl bg-accent text-xl shadow-md">
          ☕
        </div>
        <div>
          <p className="text-[10px] font-extrabold tracking-[0.18em] text-accent uppercase">
            Auto.Cafe
          </p>
          <p className="text-xs text-ink-faint">Первый запуск</p>
        </div>
      </div>

      <h1 className="mt-6 text-3xl font-extrabold text-ink">
        Создайте владельца
      </h1>
      <p className="mt-2 text-sm leading-relaxed text-ink-muted">
        Это единственная учётная запись, которую можно завести без пароля —
        дальше страница закроется навсегда. Записывать логин и пароль в
        переписку не стоит.
      </p>

      <SetupForm />
    </main>
  );
}
