import { requireSession } from "@/lib/admin-session";
import { fetchAdminBranch } from "@/lib/api";
import { AdminHeader } from "@/components/AdminHeader";
import { BranchForm } from "@/components/BranchForm";
import { LogoutButton } from "@/components/LogoutButton";
import { PasswordForm } from "@/components/PasswordForm";

export const dynamic = "force-dynamic";

export default async function AdminSettingsPage() {
  const session = await requireSession();
  const branch = await fetchAdminBranch(session);

  return (
    <main className="mx-auto min-h-dvh w-full max-w-2xl px-5 pt-8 pb-16">
      <AdminHeader
        eyebrow="Настройки"
        title="Заведение и доступ"
        hint="Смена пароля выкидывает из кабинета все остальные устройства — на этом же остаётесь вошедшими."
      />

      <div className="mt-6 space-y-4">
        {branch !== null && <BranchForm branch={branch} />}
        <PasswordForm />
        <LogoutButton />
      </div>
    </main>
  );
}
