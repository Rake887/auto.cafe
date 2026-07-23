/** Типы API-контракта — согласованы с бэкендом (FastAPI /docs). */

export interface Dish {
  id: number;
  name: string;
  description: string | null;
  price: number; // тенге, целое число
  image_url: string | null;
  /** метки ставит владелец в кабинете — угадывать их по описанию нельзя */
  is_veg: boolean;
  is_spicy: boolean;
  is_hit: boolean;
  is_chef: boolean;
  allergens: string | null;
}

export interface AdminDish {
  id: number;
  name: string;
  description: string | null;
  /** казахские версии; пусто — гостю на kk показываем русские */
  name_kk: string | null;
  description_kk: string | null;
  price: number;
  /** во сколько блюдо обходится заведению; null — ещё не считали */
  cost_price: number | null;
  image_url: string | null;
  is_active: boolean;
  sort_order: number;
  is_veg: boolean;
  is_spicy: boolean;
  is_hit: boolean;
  is_chef: boolean;
  allergens: string | null;
}

export interface AdminCategory {
  id: number;
  name: string;
  name_kk: string | null;
  sort_order: number;
  /** «HH:MM:SS» или null — часы показа гостю */
  available_from: string | null;
  available_to: string | null;
  dishes: AdminDish[];
}

export interface AdminMenu {
  branch_name: string;
  menu_disclaimer: string | null;
  categories: AdminCategory[];
}

export interface AdminBranch {
  id: number;
  name: string;
  menu_disclaimer: string | null;
  review_url: string | null;
  /** «HH:MM:SS» или null — часы приёма заказов */
  opens_at: string | null;
  closes_at: string | null;
  /** стоп-кран: выключен — заказы не принимаются независимо от часов */
  accepting_orders: boolean;
  lat: number | null;
  lon: number | null;
  geo_radius_m: number | null;
  /** публичный IP заведения: гость на его Wi-Fi заведомо в зале */
  trusted_ip: string | null;
}

export interface Zone {
  id: number;
  name: string;
  sort_order: number;
}

export interface PointOut {
  id: number;
  label: string;
  token: string;
  zone_id: number;
  zone_name: string;
  /** null, если публичный адрес неизвестен — туннель не поднят */
  menu_url: string | null;
}

export interface PointsResponse {
  site_url: string | null;
  zones: Zone[];
  points: PointOut[];
}

export interface ZoneStat {
  name: string;
  orders: number;
  revenue: number;
  average_check: number;
}

export type StaffRole = "cook" | "waiter";

export interface AdminStaff {
  id: number;
  full_name: string;
  role: StaffRole;
  /** false — уволен: кнопки в боте ему больше не приходят */
  is_active: boolean;
  /** прошёл ли /start в боте по своей ссылке */
  is_connected: boolean;
  /** непогашенное приглашение; null — уже зарегистрирован или бот выключен */
  deep_link: string | null;
}

export interface StaffInvite {
  staff_id: number;
  invite_token: string;
  deep_link: string | null;
}

export interface OpenCall {
  id: number;
  point_label: string;
  zone_name: string;
  comment: string | null;
  waiting_seconds: number;
  /** бот уже дёрнул чат повторно — вызов просрочен по SLA */
  escalated: boolean;
}

export interface OpenVisit {
  id: number;
  point_label: string;
  zone_name: string;
  orders: number;
  total: number;
  opened_at: string;
  /** хотя бы один заказ визита пришёл с координатами вне зала */
  has_remote: boolean;
  /** за стол поручились; пока нет — кухня не начинает готовить */
  confirmed: boolean;
}

export interface Pulse {
  orders_new: number;
  orders_cooking: number;
  orders_ready: number;
  /** минут ждёт самый старый непринятый заказ; null — таких нет */
  oldest_new_minutes: number | null;
  open_calls: OpenCall[];
  unresolved_reviews: number;
  open_visits: OpenVisit[];
}

export interface AdminServiceCall {
  id: number;
  created_at: string;
  point_label: string;
  zone_name: string;
  comment: string | null;
  resolved_at: string | null;
  waiting_seconds: number;
  escalated: boolean;
  taken_by: string | null;
}

export interface AdminOrderItem {
  name: string;
  qty: number;
  price: number;
}

export interface AdminOrder {
  id: number;
  /** «Терраса №14»; у заказов до появления зон — «#61» */
  number: string;
  created_at: string;
  status: OrderStatus;
  point_label: string;
  zone_name: string | null;
  total: number;
  comment: string | null;
  items: AdminOrderItem[];
  /** телефон гостя был далеко от заведения */
  is_remote: boolean;
  cooked_by: string | null;
  served_by: string | null;
  /** «за столом никого» — почему отменили; null, если причину не выбирали */
  cancel_reason: string | null;
}

export interface AdminReview {
  id: number;
  created_at: string;
  rating: number;
  comment: string | null;
  order_number: string;
  point_label: string;
  order_total: number;
  /** заполнено — владелец отметил, что разобрался */
  resolved_at: string | null;
}

export interface Category {
  id: number;
  name: string;
  dishes: Dish[];
}

export interface MenuResponse {
  branch_name: string;
  point_label: string;
  categories: Category[];
  /** предупреждение об аллергенах внизу меню; null — заведение не заполнило */
  menu_disclaimer: string | null;
  /** принимает ли заведение заказы прямо сейчас */
  accepting_orders: boolean;
  closed_reason: string | null;
  /** заведение задало координаты — есть смысл спрашивать геопозицию */
  geo_check_enabled: boolean;
}

export type OrderStatus = "new" | "accepted" | "ready" | "served" | "cancelled";

export interface OrderItemPayload {
  dish_id: number;
  qty: number;
}

export interface CreateOrderPayload {
  point_token: string;
  client_request_id: string;
  items: OrderItemPayload[];
  comment?: string | null;
  /** координаты гостя, если браузер их дал; отказ заказу не мешает */
  lat?: number | null;
  lon?: number | null;
}

export interface OrderCreated {
  order_id: number;
  status: OrderStatus;
  total: number;
}

export interface AdminTotals {
  orders: number;
  revenue: number;
  average_check: number;
  in_progress: number;
  cancelled: number;
  untouched: number;
  untouched_revenue: number;
  avg_minutes_to_served: number | null;
  /** доля себестоимости в выручке; null — себестоимость нигде не заполнена */
  food_cost_percent: number | null;
  profit: number;
  /** процент проданных порций, попавших в расчёт прибыли */
  costed_share: number;
}

export interface DishStat {
  name: string;
  qty: number;
  revenue: number;
  /** null — на момент заказа себестоимость не знали */
  profit: number | null;
}

export interface StaffStat {
  name: string;
  role: string | null;
  orders: number;
  revenue: number;
}

export interface Bucket {
  label: string;
  orders: number;
  revenue: number;
}

export interface AdminStats {
  period: string;
  branch_name: string;
  totals: AdminTotals;
  top_dishes: DishStat[];
  top_profit: DishStat[];
  waiters: StaffStat[];
  cooks: StaffStat[];
  by_hour: Bucket[];
  by_weekday: Bucket[];
  by_zone: ZoneStat[];
  /** средняя оценка гостей; null — за период не оценивали */
  rating_avg: number | null;
  rating_count: number;
}

export interface OrderItemOut {
  dish_name: string;
  qty: number;
  price: number;
}

export interface OrderState {
  id: number;
  /** короткий номер для человека: «Терраса №14» */
  number: string;
  status: OrderStatus;
  created_at: string;
  total: number;
  comment: string | null;
  cooked_by: string | null;
  served_by: string | null;
  items: OrderItemOut[];
}
