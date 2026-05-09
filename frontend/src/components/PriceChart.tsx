"use client";

import {
  Bar,
  BarChart,
  CartesianGrid,
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

// Slate-600 for non-winners, lime-600 for the cheapest bar.
const BAR_COLOR = "#475569";
const CHEAPEST_COLOR = "#16a34a";

export function PriceChart({ results }: PriceChartProps) {
  const { format, currency, rate } = useCurrency();
  const symbol = currency === "ILS" && rate !== null ? "₪" : "$";
  const multiplier = currency === "ILS" && rate !== null ? rate : 1;
  // Only successful results with a positive price are charted. Failed sites
  // are intentionally hidden — comparing a real price against "$0" or "N/A"
  // is misleading on a bar chart.
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
    <div className="w-full max-w-6xl rounded-lg border border-slate-200 bg-white shadow-sm p-6">
      <div className="mb-4 flex items-baseline justify-between">
        <h2 className="text-lg font-semibold text-slate-900">
          Price Comparison
        </h2>
        <span className="text-sm text-slate-500">
          Cheapest:{" "}
          <span className="font-semibold text-green-700">
            {priced[0].site}
          </span>{" "}
          @ {format(cheapest)}
        </span>
      </div>
      <ResponsiveContainer width="100%" height={260}>
        <BarChart
          data={data}
          margin={{ top: 24, right: 16, bottom: 8, left: 8 }}
        >
          <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
          <XAxis
            dataKey="site"
            tick={{ fill: "#475569", fontSize: 12 }}
            axisLine={{ stroke: "#cbd5e1" }}
            tickLine={false}
          />
          <YAxis
            tick={{ fill: "#475569", fontSize: 12 }}
            axisLine={{ stroke: "#cbd5e1" }}
            tickLine={false}
            tickFormatter={(v: number) => `${symbol}${v}`}
          />
          <Tooltip
            cursor={{ fill: "#f1f5f9" }}
            contentStyle={{
              borderRadius: 6,
              border: "1px solid #e2e8f0",
              fontSize: 12,
            }}
            formatter={(v: number) => `${symbol}${v.toFixed(2)}`}
          />
          <Bar dataKey="price" radius={[4, 4, 0, 0]}>
            {data.map((d) => (
              <Cell
                key={d.site}
                fill={d.isCheapest ? CHEAPEST_COLOR : BAR_COLOR}
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
              style={{ fill: "#1e293b", fontSize: 12, fontWeight: 600 }}
            />
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
