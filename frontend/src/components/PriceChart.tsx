"use client";

import {
  Bar,
  BarChart,
  Cell,
  LabelList,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { ScrapeResult } from "@/lib/types";
import { useCurrency } from "@/hooks/useCurrency";

interface PriceChartProps {
  results: ScrapeResult[];
}

interface ChartDatum {
  site: string;
  price: number;
  isCheapest: boolean;
}

// Soft-editorial palette tokens (mirror @theme in globals.css).
const COLOR_INK = "#2a2622";
const COLOR_MUTED = "#7a6f62";
const COLOR_HAIRLINE = "#ece4d7";
const COLOR_CORAL_SOFT = "#e8a896";
const COLOR_CORAL = "#c75d3f";

export function PriceChart({ results }: PriceChartProps) {
  const { format, currency, rate } = useCurrency();
  const symbol = currency === "ILS" && rate !== null ? "₪" : "$";
  const multiplier = currency === "ILS" && rate !== null ? rate : 1;

  const priced = results
    .filter(
      (r): r is ScrapeResult & { price: number } =>
        r.status === "success" && typeof r.price === "number" && r.price > 0
    )
    .sort((a, b) => a.price - b.price);

  if (priced.length === 0) {
    return null;
  }

  const cheapest = priced[0].price;
  const data: ChartDatum[] = priced.map((r) => ({
    site: r.site,
    price: r.price * multiplier,
    isCheapest: r.price === cheapest,
  }));

  return (
    <section className="w-full max-w-6xl rounded-md border hairline bg-paper p-8">
      <header className="mb-6 flex items-baseline justify-between gap-4">
        <h2 className="font-display text-2xl italic tracking-tight">
          Price comparison
        </h2>
        <p className="text-sm text-muted">
          Cheapest:{" "}
          <span className="font-display italic text-ink">
            {priced[0].site}
          </span>{" "}
          <span className="font-numeric text-sage">@ {format(cheapest)}</span>
        </p>
      </header>
      <ResponsiveContainer width="100%" height={280}>
        <BarChart
          data={data}
          margin={{ top: 28, right: 12, bottom: 8, left: 8 }}
        >
          <XAxis
            dataKey="site"
            tick={{ fill: COLOR_MUTED, fontSize: 12 }}
            axisLine={{ stroke: COLOR_HAIRLINE }}
            tickLine={false}
          />
          <YAxis
            tick={{ fill: COLOR_MUTED, fontSize: 12 }}
            axisLine={false}
            tickLine={false}
            tickFormatter={(v: number) => `${symbol}${v.toFixed(0)}`}
          />
          <Tooltip
            cursor={{ fill: "#faf6f0" }}
            contentStyle={{
              borderRadius: 4,
              border: `1px solid ${COLOR_HAIRLINE}`,
              background: "#ffffff",
              fontSize: 12,
              color: COLOR_INK,
            }}
            formatter={(v) => [
              typeof v === "number" ? `${symbol}${v.toFixed(2)}` : String(v),
              "Price",
            ]}
          />
          <Bar dataKey="price" radius={[3, 3, 0, 0]} maxBarSize={88}>
            {data.map((d) => (
              <Cell
                key={d.site}
                fill={d.isCheapest ? COLOR_CORAL : COLOR_CORAL_SOFT}
              />
            ))}
            <LabelList
              dataKey="price"
              position="top"
              formatter={(value: unknown) =>
                typeof value === "number"
                  ? `${symbol}${value.toFixed(2)}`
                  : ""
              }
              style={{
                fill: COLOR_INK,
                fontSize: 12,
                fontFamily: "var(--font-mono)",
                fontVariantNumeric: "tabular-nums",
              }}
            />
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </section>
  );
}
