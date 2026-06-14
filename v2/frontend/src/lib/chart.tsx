export const C = {
  bakery: "#b5793b",
  green: "#10b981",
  blue: "#3b82f6",
  indigo: "#6366f1",
  amber: "#f59e0b",
  red: "#ef4444",
} as const;

export const TICK = { fontSize: 11, fill: "#9ca3af" } as const;

export function mkTooltip(format: (v: number | string, name: string) => string) {
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  return (props: any) => {
    const { active, payload, label } = props as {
      active?: boolean;
      payload?: Array<{ fill?: string; color?: string; stroke?: string; name?: string; value: number | string }>;
      label?: string;
    };
    if (!active || !payload?.length) return null;
    return (
      <div className="rounded-xl border bg-card shadow-lg px-3 py-2.5 text-xs min-w-[110px]">
        {label && (
          <p className="text-muted-foreground font-medium mb-1.5 pb-1.5 border-b">{label}</p>
        )}
        {payload.map((p, i) => (
          <div key={i} className="flex items-center gap-2 py-0.5">
            <span
              className="size-2 rounded-full shrink-0"
              style={{ background: p.fill ?? p.color ?? p.stroke }}
            />
            <span className="text-muted-foreground">{p.name}</span>
            <span className="font-semibold tabular-nums ml-auto pl-2">
              {format(p.value, p.name ?? "")}
            </span>
          </div>
        ))}
      </div>
    );
  };
}
