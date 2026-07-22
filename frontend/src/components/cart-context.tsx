"use client";

import {
  createContext,
  useCallback,
  useContext,
  useMemo,
  useRef,
  useState,
} from "react";
import type { Dish } from "@/lib/types";

export interface CartLine {
  dish: Dish;
  qty: number;
}

interface CartContextValue {
  lines: CartLine[];
  count: number;
  total: number;
  qtyOf: (dishId: number) => number;
  add: (dish: Dish) => void;
  remove: (dishId: number) => void;
  clear: () => void;
  /** UUID заказа: создаётся один раз и живёт до успешной отправки —
   *  повторный тап «Оформить» не создаст на бэкенде дубль заказа. */
  getRequestId: () => string;
  resetRequestId: () => void;
}

const CartContext = createContext<CartContextValue | null>(null);

export function CartProvider({ children }: { children: React.ReactNode }) {
  const [lines, setLines] = useState<CartLine[]>([]);
  const requestIdRef = useRef<string | null>(null);

  const add = useCallback((dish: Dish) => {
    setLines((prev) => {
      const found = prev.find((l) => l.dish.id === dish.id);
      if (!found) return [...prev, { dish, qty: 1 }];
      return prev.map((l) =>
        l.dish.id === dish.id ? { ...l, qty: l.qty + 1 } : l,
      );
    });
  }, []);

  const remove = useCallback((dishId: number) => {
    setLines((prev) =>
      prev
        .map((l) => (l.dish.id === dishId ? { ...l, qty: l.qty - 1 } : l))
        .filter((l) => l.qty > 0),
    );
  }, []);

  const clear = useCallback(() => setLines([]), []);

  const getRequestId = useCallback(() => {
    if (requestIdRef.current === null) {
      requestIdRef.current = crypto.randomUUID();
    }
    return requestIdRef.current;
  }, []);

  const resetRequestId = useCallback(() => {
    requestIdRef.current = null;
  }, []);

  const value = useMemo<CartContextValue>(() => {
    const count = lines.reduce((s, l) => s + l.qty, 0);
    const total = lines.reduce((s, l) => s + l.qty * l.dish.price, 0);
    return {
      lines,
      count,
      total,
      qtyOf: (dishId) => lines.find((l) => l.dish.id === dishId)?.qty ?? 0,
      add,
      remove,
      clear,
      getRequestId,
      resetRequestId,
    };
  }, [lines, add, remove, clear, getRequestId, resetRequestId]);

  return <CartContext.Provider value={value}>{children}</CartContext.Provider>;
}

export function useCart(): CartContextValue {
  const ctx = useContext(CartContext);
  if (ctx === null) throw new Error("useCart вне CartProvider");
  return ctx;
}
