import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../lib/auth";
import { Loader2 } from "lucide-react";

export function LoginPage() {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const login = useAuth((s) => s.login);
  const navigate = useNavigate();

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    setError(null);
    try {
      await login(username, password);
      navigate("/");
    } catch (err: unknown) {
      type ApiError = { response?: { data?: { detail?: string } } };
      const apiErr = err as ApiError;
      setError(apiErr.response?.data?.detail ?? "Kirishda xatolik yuz berdi");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="min-h-screen grid place-items-center bg-gradient-to-br from-bakery-50 via-white to-bakery-100 p-4">
      <div className="w-full max-w-sm bg-card rounded-2xl shadow-xl border p-8">
        <div className="flex items-center gap-3 mb-7">
          <div className="size-11 rounded-xl bg-bakery-500 text-white grid place-items-center font-bold text-lg">
            S
          </div>
          <div>
            <div className="font-semibold text-lg">Sutli-non</div>
            <div className="text-xs text-muted-foreground">Boshqaruv paneli v2</div>
          </div>
        </div>

        <form onSubmit={onSubmit} className="space-y-4">
          <div className="space-y-1.5">
            <label className="text-sm font-medium">Foydalanuvchi nomi</label>
            <input
              className="w-full h-10 rounded-lg border bg-background px-3 text-sm focus:outline-none focus:ring-2 focus:ring-bakery-400"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              autoComplete="username"
              required
            />
          </div>
          <div className="space-y-1.5">
            <label className="text-sm font-medium">Parol</label>
            <input
              type="password"
              className="w-full h-10 rounded-lg border bg-background px-3 text-sm focus:outline-none focus:ring-2 focus:ring-bakery-400"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              autoComplete="current-password"
              required
            />
          </div>

          {error && (
            <div className="text-sm text-destructive bg-destructive/10 rounded-lg p-3">
              {error}
            </div>
          )}

          <button
            type="submit"
            disabled={loading}
            className="w-full h-10 rounded-lg bg-bakery-500 text-white font-medium hover:bg-bakery-600 transition-colors disabled:opacity-60 flex items-center justify-center gap-2"
          >
            {loading && <Loader2 className="size-4 animate-spin" />}
            Kirish
          </button>
        </form>
      </div>
    </div>
  );
}
