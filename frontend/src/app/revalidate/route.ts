import { revalidateTag } from "next/cache";
import { MENU_TAG } from "@/lib/api";
import { getSession } from "@/lib/admin-session";

/** Сброс кэша гостевого меню после правки в админке.
 *
 * Путь намеренно не под /api — этот префикс прокси отдаёт бэкенду.
 * Дёргается из браузера владельца, поэтому требует его сессию.
 */
export async function POST() {
  const session = await getSession();
  if (session === null) {
    return Response.json({ ok: false }, { status: 404 });
  }
  // { expire: 0 } — протухание сразу. Профиль "max" дал бы
  // stale-while-revalidate: владелец сохранил цену, обновил страницу гостя и
  // ещё раз увидел старую. Для правки меню это выглядит как поломка.
  revalidateTag(MENU_TAG, { expire: 0 });
  return Response.json({ ok: true });
}
