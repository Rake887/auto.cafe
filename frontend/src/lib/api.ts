/** Слой доступа к API — единственная точка переключения мок / реальный бэкенд.
 *
 * Пока NEXT_PUBLIC_API_BASE не задан — работают моки (см. mock.ts).
 * Чтобы подключить реальный бэкенд, достаточно в .env.local указать:
 *   NEXT_PUBLIC_API_BASE=http://localhost:8010
 * Больше нигде в коде ничего менять не нужно.
 */

import type {
  AdminBranch,
  AdminMenu,
  AdminOrder,
  AdminReview,
  AdminServiceCall,
  AdminStaff,
  AdminStats,
  CreateOrderPayload,
  MenuResponse,
  OrderCreated,
  OrderState,
  PointsResponse,
  Pulse,
} from "./types";
import { ApiError } from "./api-error";
import {
  mockCallWaiter,
  mockCreateOrder,
  mockFetchMenu,
  mockFetchOrder,
} from "./mock";

// Адрес для браузера: гость ходит в API снаружи (localhost:8010 или домен).
// Значение подставляется в бандл на этапе сборки.
const PUBLIC_BASE = process.env.NEXT_PUBLIC_API_BASE ?? "";
// Адрес для SSR: внутри docker-сети это имя сервиса (http://api:8000),
// снаружи контейнера переменная не задана и совпадает с публичной.
const INTERNAL_BASE = process.env.INTERNAL_API_BASE ?? PUBLIC_BASE;

const USE_MOCK = PUBLIC_BASE === "";

/** Тег кэша гостевого меню — сбрасывается после правок владельца. */
export const MENU_TAG = "menu";

/** На сервере ходим по внутреннему адресу, в браузере — по публичному. */
function base(): string {
  return typeof window === "undefined" ? INTERNAL_BASE : PUBLIC_BASE;
}

async function parseError(res: Response, fallback: string): Promise<never> {
  let message = fallback;
  try {
    const body = (await res.json()) as { detail?: string };
    if (typeof body.detail === "string") message = body.detail;
  } catch {
    // тело не JSON — оставляем fallback
  }
  throw new ApiError(res.status, message);
}

export async function fetchMenu(
  token: string,
  lang: string = "ru",
): Promise<MenuResponse> {
  if (USE_MOCK) return mockFetchMenu(token);
  // язык в адресе, а не в заголовке: у SSR-кэша разные ключи на язык,
  // и казахская версия не подменит русскую
  const res = await fetch(`${base()}/m/${encodeURIComponent(token)}?lang=${lang}`, {
    // SSR-кэш: гостям важна скорость. Тег позволяет сбросить его сразу после
    // правки меню владельцем, а 20 секунд — страховка, если сброс не дошёл.
    next: { revalidate: 20, tags: [MENU_TAG] },
  });
  if (!res.ok) await parseError(res, "Не удалось загрузить меню");
  return res.json();
}

export async function createOrder(
  payload: CreateOrderPayload,
): Promise<OrderCreated> {
  if (USE_MOCK) return mockCreateOrder(payload);
  const res = await fetch(`${base()}/orders`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!res.ok) await parseError(res, "Не удалось отправить заказ");
  return res.json();
}

/** Позвать официанта к столу. 429 — вызов уже отправлен, идёт пауза.
 *
 *  comment — пожелание гостя из шторки вызова (быстрые чипы плюс свободный
 *  текст). Уходит полем "comment" в теле запроса.
 */
export async function callWaiter(
  pointToken: string,
  comment?: string,
): Promise<void> {
  if (USE_MOCK) return mockCallWaiter(pointToken, comment);
  const res = await fetch(`${base()}/calls`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      point_token: pointToken,
      comment: comment?.trim() || null,
    }),
  });
  if (!res.ok) await parseError(res, "Не удалось позвать официанта");
}

/** Запрос к админ-API. На сервере cookie сессии не передаётся сама —
 *  её нужно явно переложить в заголовок. */
async function adminFetch(
  path: string,
  session?: string,
  init?: RequestInit,
): Promise<Response> {
  return fetch(`${base()}${path}`, {
    ...init,
    cache: "no-store",
    headers: {
      ...init?.headers,
      ...(session ? { Cookie: `qrmenu_admin=${session}` } : {}),
    },
  });
}

/** Столы заведения с их ссылками — для страницы печати QR. */
export async function fetchPoints(
  session: string,
): Promise<PointsResponse | null> {
  if (USE_MOCK) return null;
  const res = await adminFetch("/admin/points", session);
  if (res.status === 404) return null; // нет сессии или она протухла
  if (!res.ok) await parseError(res, "Не удалось загрузить список столов");
  return res.json();
}

/** Меню глазами владельца: со скрытыми блюдами и порядком. */
export async function fetchAdminMenu(session: string): Promise<AdminMenu | null> {
  if (USE_MOCK) return null;
  const res = await adminFetch("/admin/menu", session);
  if (res.status === 404) return null;
  if (!res.ok) await parseError(res, "Не удалось загрузить меню");
  return res.json();
}

/** Персонал заведения: повара и официанты, включая уволенных. */
export async function fetchAdminStaff(
  session: string,
): Promise<AdminStaff[] | null> {
  if (USE_MOCK) return null;
  const res = await adminFetch("/admin/staff", session);
  if (res.status === 404) return null;
  if (!res.ok) await parseError(res, "Не удалось загрузить персонал");
  return res.json();
}

/** Лента заказов за период — то, что видно в чате, но одним списком. */
export async function fetchAdminOrders(
  session: string,
  period: string,
): Promise<AdminOrder[] | null> {
  if (USE_MOCK) return null;
  const res = await adminFetch(`/admin/orders?period=${period}`, session);
  if (res.status === 404) return null;
  if (!res.ok) await parseError(res, "Не удалось загрузить заказы");
  return res.json();
}

/** Нужна ли первичная настройка: в базе ещё нет ни одного владельца.
 *  Без сессии — это единственная админ-ручка, отвечающая осмысленно. */
export async function fetchSetupState(): Promise<{ needs_setup: boolean } | null> {
  if (USE_MOCK) return null;
  try {
    const res = await fetch(`${base()}/admin/setup`, { cache: "no-store" });
    if (!res.ok) return null;
    return await res.json();
  } catch {
    return null; // бэкенд не отвечает — ведём на обычный вход
  }
}

/** Настройки заведения: имя, дисклеймер, ссылка на отзывы. */
export async function fetchAdminBranch(
  session: string,
): Promise<AdminBranch | null> {
  if (USE_MOCK) return null;
  const res = await adminFetch("/admin/branch", session);
  if (res.status === 404) return null;
  if (!res.ok) await parseError(res, "Не удалось загрузить настройки");
  return res.json();
}

/** Что горит в зале прямо сейчас — первый блок кабинета. */
export async function fetchPulse(session: string): Promise<Pulse | null> {
  if (USE_MOCK) return null;
  const res = await adminFetch("/admin/pulse", session);
  if (res.status === 404) return null;
  if (!res.ok) await parseError(res, "Не удалось загрузить сводку");
  return res.json();
}

/** История вызовов официанта за период. */
export async function fetchAdminCalls(
  session: string,
  period: string,
): Promise<AdminServiceCall[] | null> {
  if (USE_MOCK) return null;
  const res = await adminFetch(`/admin/calls?period=${period}`, session);
  if (res.status === 404) return null;
  if (!res.ok) await parseError(res, "Не удалось загрузить вызовы");
  return res.json();
}

/** Правки меню идут из браузера: cookie сессии уходит сама.
 *  После каждой успешной правки сбрасываем кэш гостевого меню. */
export async function adminMutate<T>(
  path: string,
  init: RequestInit = {},
): Promise<T | null> {
  const res = await fetch(`/api${path}`, {
    ...init,
    headers: init.body
      ? { "Content-Type": "application/json", ...init.headers }
      : init.headers,
  });
  if (!res.ok) await parseError(res, "Не удалось сохранить");
  await fetch("/revalidate", { method: "POST" }).catch(() => {});
  return res.status === 204 ? null : ((await res.json()) as T);
}

/** Статистика заведения. Без действующей сессии бэкенд отвечает 404. */
export async function fetchAdminStats(
  session: string,
  period: string,
): Promise<AdminStats | null> {
  if (USE_MOCK) return null;
  const res = await adminFetch(`/admin/stats?period=${period}`, session);
  if (res.status === 404) return null;
  if (!res.ok) await parseError(res, "Не удалось загрузить статистику");
  return res.json();
}

export interface DemoLink {
  public_url: string | null;
  menu_url: string | null;
  point_label: string | null;
  token: string | null;
}

/** Публичный адрес демо-меню — служебная страница «/» показывает его и QR. */
export async function fetchDemoLink(): Promise<DemoLink | null> {
  if (USE_MOCK) return null;
  try {
    const res = await fetch(`${base()}/demo/link`, { cache: "no-store" });
    if (!res.ok) return null;
    return await res.json();
  } catch {
    return null; // бэкенд не отвечает — страница покажет подсказку
  }
}

export interface ReviewResult {
  rating: number;
  /** ссылка на публичные карты — только для довольных гостей */
  review_url: string | null;
}

/** Оценка гостя после подачи. Одна на заказ: повторная отправка даёт 409. */
export async function submitReview(
  orderId: number,
  rating: number,
  comment?: string,
): Promise<ReviewResult> {
  if (USE_MOCK) return { rating, review_url: null };
  const res = await fetch(`${base()}/reviews`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      order_id: orderId,
      rating,
      comment: comment ?? null,
    }),
  });
  if (!res.ok) await parseError(res, "Не удалось отправить оценку");
  return res.json();
}

/** Отзывы гостей за период — для разбора жалоб в кабинете. */
export async function fetchAdminReviews(
  session: string,
  period: string,
): Promise<AdminReview[] | null> {
  if (USE_MOCK) return null;
  const res = await adminFetch(`/admin/reviews?period=${period}`, session);
  if (res.status === 404) return null;
  if (!res.ok) await parseError(res, "Не удалось загрузить отзывы");
  return res.json();
}

export async function fetchOrderStatus(orderId: number): Promise<OrderState> {
  if (USE_MOCK) return mockFetchOrder(orderId);
  const res = await fetch(`${base()}/orders/${orderId}`, { cache: "no-store" });
  if (!res.ok) await parseError(res, "Не удалось получить статус заказа");
  return res.json();
}
