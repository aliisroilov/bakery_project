import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Users, Plus, Pencil, Archive as ArchiveIcon, Phone, Package } from "lucide-react";
import { Link } from "react-router-dom";
import { api } from "../lib/api";
import type { Paginated, Product } from "../lib/types";

interface ApiUser {
  id: number;
  username: string;
  full_name: string;
  display_name: string;
  phone: string;
  role: string;
  is_active: boolean;
  is_archived: boolean;
  date_joined: string;
  produced_product: number | null;
  produced_product_name: string;
}

const ROLE_LABEL: Record<string, string> = {
  manager: "Menejer",
  driver: "Haydovchi",
  viewer: "Ko'ruvchi",
  nonvoy: "Nonvoy",
  accountant: "Buxgalter",
};

const ROLE_COLORS: Record<string, string> = {
  manager: "bg-blue-500/15 text-blue-700",
  driver: "bg-amber-500/15 text-amber-700",
  viewer: "bg-slate-500/15 text-slate-700",
  nonvoy: "bg-bakery-500/15 text-bakery-700",
  accountant: "bg-emerald-500/15 text-emerald-700",
};

export function UsersPage() {
  const [roleFilter, setRoleFilter] = useState<string>("");
  const [search, setSearch] = useState("");
  const [creating, setCreating] = useState(false);
  const [editing, setEditing] = useState<ApiUser | null>(null);

  const qc = useQueryClient();

  const { data: users } = useQuery<Paginated<ApiUser>>({
    queryKey: ["users", roleFilter, search],
    queryFn: async () => {
      const params: Record<string, string> = { archived: "false" };
      if (roleFilter) params.role = roleFilter;
      if (search) params.search = search;
      return (await api.get<Paginated<ApiUser>>("/users/", { params })).data;
    },
  });

  const archive = useMutation({
    mutationFn: (id: number) => api.delete(`/users/${id}/`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["users"] }),
  });

  return (
    <div className="space-y-4 sm:space-y-5">
      <div className="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-3">
        <div>
          <h1 className="text-xl sm:text-2xl font-semibold tracking-tight flex items-center gap-2">
            <Users className="size-5 sm:size-6 text-bakery-500" /> Xodimlar
          </h1>
          <p className="text-muted-foreground text-sm">
            {users?.count ?? 0} faol xodim · CRUD + jurnal (<Link className="underline" to="/logs">Loglar →</Link>)
          </p>
        </div>
        <button
          onClick={() => setCreating(true)}
          className="inline-flex items-center justify-center gap-1 h-10 px-4 rounded-lg bg-bakery-500 hover:bg-bakery-600 text-white text-sm w-full sm:w-auto"
        >
          <Plus className="size-4" /> Yangi xodim
        </button>
      </div>

      <div className="rounded-xl border bg-card p-3 sm:p-4 grid grid-cols-2 sm:flex sm:flex-wrap sm:items-end gap-3">
        <div>
          <label className="block text-xs text-muted-foreground mb-1">Rol</label>
          <select
            value={roleFilter}
            onChange={(e) => setRoleFilter(e.target.value)}
            className="h-10 w-full rounded-lg border bg-background px-3 text-sm"
          >
            <option value="">Barchasi</option>
            {Object.entries(ROLE_LABEL).map(([k, v]) => (
              <option key={k} value={k}>
                {v}
              </option>
            ))}
          </select>
        </div>
        <div className="col-span-2 sm:flex-1 sm:min-w-[200px]">
          <label className="block text-xs text-muted-foreground mb-1">Qidiruv</label>
          <input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Ism, username yoki telefon…"
            className="h-10 w-full rounded-lg border bg-background px-3 text-sm"
          />
        </div>
      </div>

      {/* Desktop table */}
      <div className="rounded-xl border bg-card overflow-hidden hidden md:block">
        <table className="w-full text-sm">
          <thead className="bg-muted/50 text-xs text-muted-foreground">
            <tr>
              <th className="text-left px-4 py-3 font-medium">Ism</th>
              <th className="text-left px-4 py-3 font-medium">Username</th>
              <th className="text-left px-4 py-3 font-medium">Rol</th>
              <th className="text-left px-4 py-3 font-medium">Mahsulot</th>
              <th className="text-left px-4 py-3 font-medium">Telefon</th>
              <th className="text-right px-4 py-3 font-medium w-40"></th>
            </tr>
          </thead>
          <tbody className="divide-y">
            {users?.results.length === 0 && (
              <tr>
                <td colSpan={6} className="px-4 py-10 text-center text-muted-foreground">
                  Xodim topilmadi
                </td>
              </tr>
            )}
            {users?.results.map((u) => (
              <tr key={u.id} className="hover:bg-muted/30">
                <td className="px-4 py-3 font-medium">{u.display_name}</td>
                <td className="px-4 py-3 text-muted-foreground font-mono text-xs">{u.username}</td>
                <td className="px-4 py-3">
                  <span
                    className={
                      "inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium " +
                      (ROLE_COLORS[u.role] ?? "bg-muted")
                    }
                  >
                    {ROLE_LABEL[u.role] ?? u.role}
                  </span>
                </td>
                <td className="px-4 py-3 text-muted-foreground">
                  {u.produced_product_name ? (
                    <span className="inline-flex items-center gap-1 text-xs">
                      <Package className="size-3" /> {u.produced_product_name}
                    </span>
                  ) : (
                    "—"
                  )}
                </td>
                <td className="px-4 py-3 text-muted-foreground">
                  {u.phone ? (
                    <span className="inline-flex items-center gap-1">
                      <Phone className="size-3" /> {u.phone}
                    </span>
                  ) : (
                    "—"
                  )}
                </td>
                <td className="px-4 py-3 text-right space-x-2">
                  <button
                    onClick={() => setEditing(u)}
                    className="inline-flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground"
                  >
                    <Pencil className="size-3.5" /> Tahrir
                  </button>
                  <button
                    onClick={() => {
                      if (confirm(`${u.display_name} — arxivga o'tkazilsinmi?`)) {
                        archive.mutate(u.id);
                      }
                    }}
                    className="inline-flex items-center gap-1 text-xs text-destructive hover:underline"
                  >
                    <ArchiveIcon className="size-3.5" /> Arxiv
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Mobile cards */}
      <div className="md:hidden space-y-2">
        {users?.results.length === 0 && (
          <div className="rounded-xl border bg-card px-4 py-10 text-center text-muted-foreground text-sm">
            Xodim topilmadi
          </div>
        )}
        {users?.results.map((u) => (
          <div key={u.id} className="rounded-xl border bg-card p-3 space-y-2">
            <div className="flex items-start justify-between gap-2">
              <div className="min-w-0 flex-1">
                <div className="font-medium truncate">{u.display_name}</div>
                <div className="text-xs text-muted-foreground font-mono truncate">
                  @{u.username}
                </div>
              </div>
              <span
                className={
                  "inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-medium shrink-0 " +
                  (ROLE_COLORS[u.role] ?? "bg-muted")
                }
              >
                {ROLE_LABEL[u.role] ?? u.role}
              </span>
            </div>
            <div className="flex flex-wrap gap-x-3 gap-y-1 text-xs text-muted-foreground">
              {u.phone && (
                <span className="inline-flex items-center gap-1">
                  <Phone className="size-3" /> {u.phone}
                </span>
              )}
              {u.produced_product_name && (
                <span className="inline-flex items-center gap-1">
                  <Package className="size-3" /> {u.produced_product_name}
                </span>
              )}
            </div>
            <div className="flex items-center gap-2 pt-1 border-t">
              <button
                onClick={() => setEditing(u)}
                className="flex-1 inline-flex items-center justify-center gap-1 h-8 text-xs rounded-lg border hover:bg-muted"
              >
                <Pencil className="size-3.5" /> Tahrir
              </button>
              <button
                onClick={() => {
                  if (confirm(`${u.display_name} — arxivga o'tkazilsinmi?`)) {
                    archive.mutate(u.id);
                  }
                }}
                className="flex-1 inline-flex items-center justify-center gap-1 h-8 text-xs rounded-lg border text-destructive hover:bg-destructive/10"
              >
                <ArchiveIcon className="size-3.5" /> Arxiv
              </button>
            </div>
          </div>
        ))}
      </div>

      {creating && <UserModal onClose={() => setCreating(false)} />}
      {editing && <UserModal user={editing} onClose={() => setEditing(null)} />}
    </div>
  );
}

function UserModal({
  user,
  onClose,
}: {
  user?: ApiUser;
  onClose: () => void;
}) {
  const qc = useQueryClient();
  const isEdit = !!user;
  const [username, setUsername] = useState(user?.username ?? "");
  const [fullName, setFullName] = useState(user?.full_name ?? "");
  const [role, setRole] = useState(user?.role ?? "driver");
  const [phone, setPhone] = useState(user?.phone ?? "");
  const [password, setPassword] = useState("");
  const [producedProduct, setProducedProduct] = useState<number | "">(
    user?.produced_product ?? "",
  );

  const { data: products } = useQuery<Paginated<Product>>({
    queryKey: ["products", "for-user-modal"],
    queryFn: async () => (await api.get<Paginated<Product>>("/products/")).data,
    enabled: role === "nonvoy",
  });

  const save = useMutation({
    mutationFn: () => {
      const payload: Record<string, string | number | null> = {
        username,
        full_name: fullName,
        role,
        phone,
      };
      if (password) payload.password = password;
      payload.produced_product =
        role === "nonvoy" && producedProduct ? Number(producedProduct) : null;
      if (isEdit) return api.patch(`/users/${user!.id}/`, payload);
      return api.post("/users/", payload);
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["users"] });
      onClose();
    },
  });

  const canSave = username.trim() && (isEdit || password.trim());

  return (
    <div className="fixed inset-0 grid place-items-center bg-black/30 p-3 sm:p-4 z-50" onClick={onClose}>
      <div
        onClick={(e) => e.stopPropagation()}
        className="w-full max-w-md bg-card rounded-2xl shadow-xl border p-4 sm:p-6 max-h-[90vh] overflow-y-auto"
      >
        <h2 className="font-semibold text-lg mb-4">
          {isEdit ? "Xodimni tahrirlash" : "Yangi xodim"}
        </h2>
        <div className="space-y-3">
          <Field label="Username">
            <input
              className="w-full h-10 px-3 rounded-lg border bg-background text-sm"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              disabled={isEdit}
            />
          </Field>
          <Field label="To'liq ism">
            <input
              className="w-full h-10 px-3 rounded-lg border bg-background text-sm"
              value={fullName}
              onChange={(e) => setFullName(e.target.value)}
            />
          </Field>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <Field label="Rol">
              <select
                value={role}
                onChange={(e) => setRole(e.target.value)}
                className="w-full h-10 rounded-lg border bg-background px-3 text-sm"
              >
                {Object.entries(ROLE_LABEL).map(([k, v]) => (
                  <option key={k} value={k}>
                    {v}
                  </option>
                ))}
              </select>
            </Field>
            <Field label="Telefon">
              <input
                className="w-full h-10 px-3 rounded-lg border bg-background text-sm"
                value={phone}
                onChange={(e) => setPhone(e.target.value)}
                placeholder="+998 90 123 45 67"
              />
            </Field>
          </div>
          <Field label={isEdit ? "Yangi parol (bo'sh qoldiring = o'zgarishsiz)" : "Parol"}>
            <input
              type="password"
              className="w-full h-10 px-3 rounded-lg border bg-background text-sm"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder={isEdit ? "••••••••" : "Kamida 6 ta belgi"}
            />
          </Field>
          {role === "nonvoy" && (
            <Field label="Qaysi mahsulotni ishlab chiqaradi">
              <select
                value={producedProduct}
                onChange={(e) =>
                  setProducedProduct(e.target.value ? Number(e.target.value) : "")
                }
                className="w-full h-10 px-3 rounded-lg border bg-background text-sm"
              >
                <option value="">— Tanlanmagan —</option>
                {products?.results.map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.name}
                  </option>
                ))}
              </select>
            </Field>
          )}
        </div>
        {save.isError && (
          <div className="mt-3 text-sm text-destructive bg-destructive/10 rounded-lg p-3">
            Saqlashda xatolik.
          </div>
        )}
        <div className="mt-5 flex flex-col-reverse sm:flex-row sm:justify-end gap-2">
          <button
            onClick={onClose}
            className="h-10 px-4 rounded-lg border text-sm hover:bg-muted"
          >
            Bekor qilish
          </button>
          <button
            disabled={!canSave || save.isPending}
            onClick={() => save.mutate()}
            className="h-10 px-4 rounded-lg bg-bakery-500 hover:bg-bakery-600 text-white text-sm disabled:opacity-50"
          >
            Saqlash
          </button>
        </div>
      </div>
    </div>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div>
      <label className="block text-xs text-muted-foreground mb-1">{label}</label>
      {children}
    </div>
  );
}
