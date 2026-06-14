import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Archive, ArchiveRestore, Store, Package, Users, Wheat } from "lucide-react";
import { api } from "../lib/api";
import type { Paginated, Product, Shop } from "../lib/types";

interface ArchivedUser {
  id: number;
  display_name: string;
  role: string;
}

interface ArchivedIngredient {
  id: number;
  name: string;
  unit_name?: string;
}

export function ArchivePage() {
  const qc = useQueryClient();

  const { data: shops } = useQuery<Paginated<Shop>>({
    queryKey: ["archive", "shops"],
    queryFn: async () =>
      (await api.get<Paginated<Shop>>("/shops/?archived=true")).data,
  });
  const { data: products } = useQuery<Paginated<Product>>({
    queryKey: ["archive", "products"],
    queryFn: async () =>
      (await api.get<Paginated<Product>>("/products/?archived=true")).data,
  });
  const { data: users } = useQuery<Paginated<ArchivedUser>>({
    queryKey: ["archive", "users"],
    queryFn: async () =>
      (await api.get<Paginated<ArchivedUser>>("/users/?archived=true")).data,
  });
  const { data: ingredients } = useQuery<Paginated<ArchivedIngredient>>({
    queryKey: ["archive", "ingredients"],
    queryFn: async () =>
      (await api.get<Paginated<ArchivedIngredient>>("/inventory/ingredients/?archived=true")).data,
  });

  // Restore = POST /{resource}/{id}/unarchive/. Invalidates both the archive
  // list and the resource's own active list so the item reappears everywhere.
  const restore = (resource: string, ownKey: string) => ({
    mutationFn: (id: number) => api.post(`/${resource}/${id}/unarchive/`),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["archive"] });
      qc.invalidateQueries({ queryKey: [ownKey] });
    },
  });

  const restoreShop = useMutation(restore("shops", "shops"));
  const restoreProduct = useMutation(restore("products", "products"));
  const restoreUser = useMutation(restore("users", "users"));
  const restoreIngredient = useMutation(restore("inventory/ingredients", "inventory"));

  return (
    <div className="space-y-4 sm:space-y-5">
      <div>
        <h1 className="text-xl sm:text-2xl font-semibold tracking-tight flex items-center gap-2">
          <Archive className="size-5 sm:size-6 text-bakery-500" /> Arxiv
        </h1>
        <p className="text-muted-foreground text-sm">
          Faoliyatdan chiqarilgan do'kon, mahsulot, xodim va xomashyolar — qaytarib olish mumkin
        </p>
      </div>

      <div className="grid gap-3 sm:gap-4 lg:grid-cols-2 xl:grid-cols-4">
        <Section
          icon={<Store className="size-4 text-muted-foreground" />}
          title="Do'konlar"
          restoring={restoreShop.isPending ? restoreShop.variables : null}
          onRestore={(id) => restoreShop.mutate(id)}
          items={
            shops?.results.map((s) => ({
              id: s.id,
              primary: s.name,
              secondary: s.region_name,
            })) ?? []
          }
        />
        <Section
          icon={<Package className="size-4 text-muted-foreground" />}
          title="Mahsulotlar"
          restoring={restoreProduct.isPending ? restoreProduct.variables : null}
          onRestore={(id) => restoreProduct.mutate(id)}
          items={
            products?.results.map((p) => ({
              id: p.id,
              primary: p.name,
              secondary: "",
            })) ?? []
          }
        />
        <Section
          icon={<Users className="size-4 text-muted-foreground" />}
          title="Xodimlar"
          restoring={restoreUser.isPending ? restoreUser.variables : null}
          onRestore={(id) => restoreUser.mutate(id)}
          items={
            users?.results.map((u) => ({
              id: u.id,
              primary: u.display_name,
              secondary: u.role,
            })) ?? []
          }
        />
        <Section
          icon={<Wheat className="size-4 text-muted-foreground" />}
          title="Xomashyolar"
          restoring={restoreIngredient.isPending ? restoreIngredient.variables : null}
          onRestore={(id) => restoreIngredient.mutate(id)}
          items={
            ingredients?.results.map((i) => ({
              id: i.id,
              primary: i.name,
              secondary: i.unit_name ?? "",
            })) ?? []
          }
        />
      </div>
    </div>
  );
}

function Section({
  icon,
  title,
  items,
  onRestore,
  restoring,
}: {
  icon: React.ReactNode;
  title: string;
  items: { id: number; primary: string; secondary: string }[];
  onRestore: (id: number) => void;
  restoring: number | null | undefined;
}) {
  return (
    <div className="rounded-xl border bg-card overflow-hidden">
      <div className="px-4 sm:px-5 py-3 sm:py-4 border-b">
        <h2 className="font-semibold flex items-center gap-2">
          {icon} {title}
          {items.length > 0 && (
            <span className="ml-auto text-xs text-muted-foreground font-normal">{items.length}</span>
          )}
        </h2>
      </div>
      <ul className="divide-y text-sm max-h-96 overflow-auto">
        {items.length === 0 && (
          <li className="py-8 text-center text-muted-foreground text-xs">
            Arxivda hech narsa yo'q
          </li>
        )}
        {items.map((it) => (
          <li key={it.id} className="px-4 sm:px-5 py-3 flex items-center gap-2">
            <div className="min-w-0 flex-1">
              <div className="font-medium truncate">{it.primary}</div>
              {it.secondary && (
                <div className="text-xs text-muted-foreground truncate">{it.secondary}</div>
              )}
            </div>
            <button
              onClick={() => onRestore(it.id)}
              disabled={restoring === it.id}
              className="inline-flex items-center gap-1 h-8 px-2.5 rounded-lg border text-xs text-emerald-700 dark:text-emerald-400 hover:bg-emerald-50 dark:hover:bg-emerald-950/30 disabled:opacity-50 shrink-0"
              title="Arxivdan chiqarish"
            >
              <ArchiveRestore className="size-3.5" />
              <span className="hidden sm:inline">{restoring === it.id ? "..." : "Qaytarish"}</span>
            </button>
          </li>
        ))}
      </ul>
    </div>
  );
}
