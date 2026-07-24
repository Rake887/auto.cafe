/** Мок-данные и мок-API: повторяют контракт бэкенда 1:1.
 *
 * Позволяют верстать и проходить сценарий целиком без бэкенда.
 * Токен "invalid" отдаёт 404 — для проверки экрана ошибки.
 * Статус мок-заказа «готовится» сам по времени: new -> accepted -> ready -> served.
 */

import type {
  CreateOrderPayload,
  Dish,
  MenuResponse,
  OrderCreated,
  OrderState,
} from "./types";
import { ApiError } from "./api-error";

const img = (seed: string) => `https://picsum.photos/seed/${seed}/160/160`;

/** Блюдо с метками по умолчанию: в моке, как и в базе, метки выключены,
 *  пока их явно не проставили. */
function dish(
  id: number,
  name: string,
  description: string,
  price: number,
  seed: string,
  tags: Partial<Pick<Dish, "is_veg" | "is_spicy" | "is_hit" | "is_chef" | "allergens">> = {},
): Dish {
  return {
    id,
    name,
    description,
    price,
    image_url: img(seed),
    is_veg: false,
    is_spicy: false,
    is_hit: false,
    is_chef: false,
    allergens: null,
    ...tags,
  };
}

export const MOCK_MENU: MenuResponse = {
  branch_name: "Кафе «Тараз»",
  point_label: "Стол 3",
  menu_disclaimer:
    "Блюда готовятся на одной кухне: следы орехов, глютена и молока возможны в любой позиции. О непереносимости предупредите официанта.",
  accepting_orders: true,
  closed_reason: null,
  geo_check_enabled: false,
  categories: [
    {
      id: 1,
      name: "Горячие блюда",
      dishes: [
        dish(1, "Плов по-тараски", "Баранина, жёлтая морковь, нут, казан. Порция 350 г", 2500, "qrmenu-0-0", { is_hit: true }),
        dish(2, "Лагман", "Тянутая лапша ручной работы, говядина, болгарский перец", 2200, "qrmenu-0-1", { allergens: "глютен" }),
        dish(3, "Манты (5 шт.)", "Рубленая баранина с луком, тесто раскатано вручную", 1800, "qrmenu-0-2", { allergens: "глютен" }),
        dish(4, "Бешбармак", "Отварное мясо с кеспе и луковым соусом. На двоих", 3200, "qrmenu-0-3", { is_chef: true, allergens: "глютен" }),
        dish(5, "Куырдак", "Жаркое из баранины с картофелем и специями", 2600, "qrmenu-0-4"),
      ],
    },
    {
      id: 2,
      name: "Салаты",
      dishes: [
        dish(6, "Салат «Ачичук»", "Томаты, красный лук, зелень, немного острого перца", 1200, "qrmenu-1-0", { is_veg: true, is_spicy: true }),
        dish(7, "Цезарь с курицей", "Ромэн, куриное филе на гриле, пармезан, сухарики", 1900, "qrmenu-1-1", { allergens: "молоко, глютен, яйцо" }),
        dish(8, "Овощной салат", "Огурцы, помидоры, редис, зелень, оливковое масло", 1100, "qrmenu-1-2", { is_veg: true }),
      ],
    },
    {
      id: 3,
      name: "Напитки",
      dishes: [
        dish(9, "Чай (чайник)", "Чёрный или зелёный, чайник 1 л на компанию", 800, "qrmenu-2-0", { is_veg: true }),
        dish(10, "Американо", "Двойной эспрессо с горячей водой, 250 мл", 900, "qrmenu-2-1", { is_veg: true }),
        dish(11, "Капучино", "Эспрессо и взбитое молоко, 300 мл", 1100, "qrmenu-2-2", { is_veg: true, allergens: "молоко" }),
        dish(12, "Морс клюквенный", "Домашний, не сладкий, подаётся холодным", 700, "qrmenu-2-3", { is_veg: true }),
      ],
    },
    {
      id: 4,
      name: "Десерты",
      dishes: [
        dish(13, "Чак-чак", "Хрустящее тесто в медовом сиропе, порция 150 г", 900, "qrmenu-3-0", { is_veg: true, allergens: "глютен, яйцо, мёд" }),
        dish(14, "Медовик", "Десять коржей со сметанным кремом", 1300, "qrmenu-3-1", { is_veg: true, allergens: "молоко, глютен, яйцо" }),
      ],
    },
  ],
};

const delay = (ms: number) => new Promise((r) => setTimeout(r, ms));

export async function mockFetchMenu(token: string): Promise<MenuResponse> {
  await delay(400);
  if (token === "invalid") {
    throw new ApiError(404, "Стол с таким QR-кодом не найден");
  }
  return MOCK_MENU;
}

const allDishes = MOCK_MENU.categories.flatMap((c) => c.dishes);
// повторный POST с тем же client_request_id вернёт тот же заказ (идемпотентность как на бэке)
const ordersByRequestId = new Map<string, OrderCreated>();
// состав заказов по id — чтобы экран статуса мог показать, что заказали
const itemsByOrderId = new Map<number, OrderState["items"]>();
const commentByOrderId = new Map<number, string | null>();
// время последнего вызова официанта по столам — повторяем антиспам бэкенда
const lastCallByToken = new Map<string, number>();

export async function mockCreateOrder(
  payload: CreateOrderPayload,
): Promise<OrderCreated> {
  await delay(600);
  const existing = ordersByRequestId.get(payload.client_request_id);
  if (existing) return existing;

  const lines = payload.items.map((item) => {
    const dish = allDishes.find((d) => d.id === item.dish_id);
    return {
      dish_name: dish?.name ?? "Блюдо",
      qty: item.qty,
      price: dish?.price ?? 0,
      // отметить «кончилось» может только официант из бота — мок этого не умеет
      unavailable: false,
    };
  });
  const total = lines.reduce((sum, l) => sum + l.price * l.qty, 0);
  // id мок-заказа = timestamp создания: статус ниже вычисляется из прошедшего
  // времени и переживает перезагрузку страницы
  const order: OrderCreated = { order_id: Date.now(), status: "new", total };
  ordersByRequestId.set(payload.client_request_id, order);
  itemsByOrderId.set(order.order_id, lines);
  commentByOrderId.set(order.order_id, payload.comment?.trim() || null);
  return order;
}

export async function mockCallWaiter(
  pointToken: string,
  // мок пожелание не хранит, но сигнатура должна совпадать с реальным api
  _comment?: string,
): Promise<void> {
  await delay(400);
  const last = lastCallByToken.get(pointToken) ?? 0;
  if ((Date.now() - last) / 1000 < 60) {
    throw new ApiError(429, "Официант уже вызван, подождите минуту");
  }
  lastCallByToken.set(pointToken, Date.now());
}

// id мок-заказа = момент создания, поэтому статус выводится из возраста
function mockStatus(orderId: number): OrderState["status"] {
  const elapsedSec = (Date.now() - orderId) / 1000;
  return elapsedSec < 8 ? "new" : elapsedSec < 20 ? "accepted" : elapsedSec < 30 ? "ready" : "served";
}

const mockNumber = (orderId: number) => `Основной зал №${(orderId % 90) + 1}`;
const mockTotal = (orderId: number) =>
  (itemsByOrderId.get(orderId) ?? []).reduce((sum, l) => sum + l.price * l.qty, 0);

export async function mockFetchOrder(orderId: number): Promise<OrderState> {
  await delay(200);
  const status = mockStatus(orderId);
  const items = itemsByOrderId.get(orderId) ?? [];
  // мок-заведение однозальное, все заказы сессии считаем одним визитом —
  // иначе блок «Ваш стол» нельзя было бы посмотреть без бэкенда
  const visitIds = [...itemsByOrderId.keys()].sort((a, b) => a - b);
  return {
    id: orderId,
    number: mockNumber(orderId),
    status,
    created_at: new Date(orderId).toISOString(),
    total: mockTotal(orderId),
    comment: commentByOrderId.get(orderId) ?? null,
    // в моках сотрудники условные — экран статуса всё равно должен их показать
    cooked_by: status === "new" ? null : "Асхат",
    served_by: status === "served" ? "Данияр" : null,
    items,
    visit:
      visitIds.length < 2
        ? null
        : {
            point_label: "Стол 12",
            orders: visitIds.map((id) => ({
              id,
              number: mockNumber(id),
              status: mockStatus(id),
              total: mockTotal(id),
            })),
            total: visitIds.reduce((sum, id) => sum + mockTotal(id), 0),
          },
  };
}
