/**
 * Auth store (Zustand). Holds current user + login/logout actions.
 */
import { create } from "zustand";
import { api, tokens } from "./api";

export type Role =
  | "manager"
  | "driver"
  | "viewer"
  | "nonvoy"
  | "accountant";

export interface CurrentUser {
  id: number;
  username: string;
  role: Role;
  full_name?: string;
  display_name?: string;
  is_superuser: boolean;
}

interface AuthState {
  user: CurrentUser | null;
  loading: boolean;
  login: (username: string, password: string) => Promise<void>;
  logout: () => void;
  loadMe: () => Promise<void>;
}

export const useAuth = create<AuthState>((set) => ({
  user: null,
  loading: true,

  async login(username, password) {
    const res = await api.post("/auth/login/", { username, password });
    tokens.set(res.data.access, res.data.refresh);
    await useAuth.getState().loadMe();
  },

  logout() {
    tokens.clear();
    set({ user: null });
  },

  async loadMe() {
    if (!tokens.access) {
      set({ user: null, loading: false });
      return;
    }
    try {
      const res = await api.get<CurrentUser>("/users/me/");
      set({ user: res.data, loading: false });
    } catch {
      tokens.clear();
      set({ user: null, loading: false });
    }
  },
}));
