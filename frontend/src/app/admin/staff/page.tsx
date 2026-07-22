import { redirect } from "next/navigation";
import { requireSession } from "@/lib/admin-session";
import { fetchAdminStaff } from "@/lib/api";
import { AdminHeader } from "@/components/AdminHeader";
import { StaffManager } from "@/components/StaffManager";

// Состав смены меняется в течение дня — кэш здесь только мешает
export const dynamic = "force-dynamic";

export default async function AdminStaffPage() {
  const session = await requireSession();
  const staff = await fetchAdminStaff(session);
  if (staff === null) redirect("/admin/login");

  return (
    <main className="mx-auto min-h-dvh w-full max-w-2xl px-5 pt-8 pb-16">
      <AdminHeader
        eyebrow="Персонал"
        title="Повара и официанты"
        hint="Сотрудник открывает свою ссылку в Telegram, жмёт «Start» — и в чат заведения ему начинают приходить кнопки заказов. Ссылка одноразовая и личная: по ней в чат попадает конкретный человек."
      />

      <StaffManager staff={staff} />
    </main>
  );
}
