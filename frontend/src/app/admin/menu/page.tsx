import { redirect } from "next/navigation";
import { requireSession } from "@/lib/admin-session";
import { fetchAdminMenu } from "@/lib/api";
import { AdminHeader } from "@/components/AdminHeader";
import { MenuEditor } from "@/components/MenuEditor";

export const dynamic = "force-dynamic";

export default async function AdminMenuPage() {
  const session = await requireSession();
  const menu = await fetchAdminMenu(session);
  if (menu === null) redirect("/admin/login");

  return (
    <main className="mx-auto min-h-dvh w-full max-w-2xl px-5 pt-8 pb-16">
      <AdminHeader
        eyebrow="Меню"
        title={menu.branch_name}
        hint="Изменения видны гостям сразу. Блюдо в стоп-листе остаётся здесь, но исчезает из меню на столах."
      />

      <MenuEditor initial={menu} />
    </main>
  );
}
