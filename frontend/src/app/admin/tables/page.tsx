import { redirect } from "next/navigation";
import { requireSession } from "@/lib/admin-session";
import { fetchPoints } from "@/lib/api";
import { AdminHeader } from "@/components/AdminHeader";
import { TablesManager } from "@/components/TablesManager";

export const dynamic = "force-dynamic";

export default async function AdminTablesPage() {
  const session = await requireSession();
  const data = await fetchPoints(session);
  if (data === null) redirect("/admin/login");

  return (
    <main className="mx-auto min-h-dvh w-full max-w-2xl px-5 pt-8 pb-16">
      <AdminHeader
        eyebrow="Столы"
        title="Залы и точки заказа"
        hint="У каждого стола свой QR: по нему заказ приходит в чат с номером стола. В каждой зоне заказы нумеруются отдельно — «Терраса №1», «Зал №1» — и счёт начинается заново каждый день."
      />

      <TablesManager zones={data.zones} points={data.points} />
    </main>
  );
}
