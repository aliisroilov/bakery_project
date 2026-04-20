import { useQuery } from "@tanstack/react-query";
import { Archive, Store, Package, Users } from "lucide-react";
import { api } from "../lib/api";
import type { Paginated, Product, Shop } from "../lib/types";

interface ArchivedUser {
  id: number;
  display_name: string;
  role: string;
}

export function ArchivePage() {
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

  return (
    <div className="space-y-4 sm:space-y-5">
      <div>
        <h1 className="text-xl sm:text-2xl font-semibold tracking-tight flex items-center gap-2">
          <Archive className="size-5 sm:size-6 text-bakery-500" /> Arxiv
        </h1>
        <p className="text-muted-foreground text-sm">
          Faoliyatdan chiqarilgan do'konlar, mahsulotlar va xodimlar (feature #22)
        </p>
      </div>

      <div className="grid gap-3 sm:gap-4 lg:grid-cols-3">
        <Section
          icon={<Store className="size-4 text-muted-foreground" />}
          title="Do'konlar"
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
          items={
            users?.results.map((u) => ({
              id: u.id,
              primary: u.display_name,
              secondary: u.role,
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
}: {
  icon: React.ReactNode;
  title: string;
  items: { id: number; primary: string; secondary: string }[];
}) {
  return (
    <div className="rounded-xl border bg-card overflow-hidden">
      <div className="px-4 sm:px-5 py-3 sm:py-4 border-b">
        <h2 className="font-semibold flex items-center gap-2">
          {icon} {title}
        </h2>
      </div>
      <ul className="divide-y text-sm max-h-96 overflow-auto">
        {items.length === 0 && (
          <li className="py-8 text-center text-muted-foreground text-xs">
            Arxivda hech narsa yo'q
          </li>
        )}
        {items.map((it) => (
          <li key={it.id} className="px-4 sm:px-5 py-3">
            <div className="font-medium">{it.primary}</div>
            {it.secondary && (
              <div className="text-xs text-muted-foreground">{it.secondary}</div>
            )}
          </li>
        ))}
      </ul>
    </div>
  );
}
