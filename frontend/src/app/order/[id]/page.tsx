import { OrderStatusScreen } from "@/components/OrderStatusScreen";
import { resolveLang } from "@/lib/lang-server";

export default async function OrderPage({
  params,
  searchParams,
}: {
  params: Promise<{ id: string }>;
  searchParams: Promise<{ [key: string]: string | string[] | undefined }>;
}) {
  const { id } = await params;
  // ?t=<токен стола> — чтобы с экрана статуса можно было вернуться в своё меню
  const query = await searchParams;
  const lang = await resolveLang(query);
  return (
    <OrderStatusScreen
      orderId={Number(id)}
      token={typeof query.t === "string" ? query.t : undefined}
      lang={lang}
    />
  );
}
