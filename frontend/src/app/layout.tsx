import type { Metadata, Viewport } from "next";
import { PT_Serif, Manrope } from "next/font/google";
import "./globals.css";

// Премиальная типографика: PT Serif — заголовки (полная кириллица + казахские
// глифы ә ғ қ ң ө ұ ү һ і, в отличие от Cormorant), Manrope — текст/интерфейс.
// Оба из списка проверенных шрифтов ТЗ. Подключены через next/font: шрифт
// самохостится, ноль запросов к Google на рантайме, без layout shift.
// Только 700: все заголовки в интерфейсе жирные, обычное начертание
// не рисовалось нигде и просто тянуло три лишних файла.
// Подмножество cyrillic-ext обязательно — казахские глифы ә ғ қ ң ө ұ ү һ і
// лежат именно в нём, без него на локали kk будут квадраты.
const heading = PT_Serif({
  subsets: ["latin", "cyrillic", "cyrillic-ext"],
  weight: ["700"],
  variable: "--font-heading-src",
  display: "swap",
});

const body = Manrope({
  subsets: ["latin", "cyrillic", "cyrillic-ext"],
  weight: ["400", "500", "600", "700"],
  variable: "--font-body-src",
  display: "swap",
});

export const metadata: Metadata = {
  title: "QR-меню",
  description: "Меню и заказ со стола по QR-коду",
};

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  // Цвет строки состояния телефона под тему: иначе в тёмной теме сверху
  // остаётся светлая полоса
  themeColor: [
    { media: "(prefers-color-scheme: light)", color: "#faf7f1" },
    { media: "(prefers-color-scheme: dark)", color: "#17120f" },
  ],
  colorScheme: "light dark",
  // На вырезанных экранах контент уходит под чёлку — учитываем safe-area
  // (шапка меню использует env(safe-area-inset-top), см. MenuScreen).
  viewportFit: "cover",
};

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="ru" className={`${heading.variable} ${body.variable}`}>
      <body>{children}</body>
    </html>
  );
}
