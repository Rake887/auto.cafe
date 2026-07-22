"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";

/** Общий обработчик правок в кабинете.
 *
 *  Страницы разделов серверные и помечены force-dynamic, поэтому после
 *  успешной правки достаточно router.refresh() — сервер перерисует список
 *  заново, и экран гарантированно совпадёт с базой.
 */
export function useAdminAction() {
  const router = useRouter();
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function run(action: () => Promise<unknown>): Promise<boolean> {
    setBusy(true);
    setError(null);
    try {
      await action();
      router.refresh();
      return true;
    } catch (e) {
      setError(e instanceof Error ? e.message : "Не удалось сохранить");
      return false;
    } finally {
      setBusy(false);
    }
  }

  return { error, busy, run };
}
