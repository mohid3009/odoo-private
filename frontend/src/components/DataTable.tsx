import PageLoader from "./PageLoader";
import { ReactNode, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api } from "../api/client";
import type { Page } from "../api/types";

export interface Column<T> {
  key: string;
  header: string;
  render?: (row: T) => ReactNode;
}

interface Props<T> {
  queryKey: string; // invalidate [queryKey] after a mutation
  endpoint: string;
  columns: Column<T>[];
  params?: Record<string, string>; // filters -> query string
  empty?: string;
  onRowClick?: (row: T) => void;
}

// Server-paginated (25/page) table: new list screens are a config object, not a component (rule 10).
export default function DataTable<T extends { id: number | string }>({ queryKey, endpoint, columns, params, empty = "Nothing here yet.", onRowClick }: Props<T>) {
  const [page, setPage] = useState(1);
  const qs = new URLSearchParams({ ...params, page: String(page) }).toString();
  const { data, isLoading, isError, isFetching } = useQuery({
    queryKey: [queryKey, "list", params, page],
    queryFn: () => api.get<Page<T>>(`${endpoint}?${qs}`),
    placeholderData: (prev) => prev,
  });

  if (isLoading) return <PageLoader />;
  if (isError || !data) return <p className="py-6 text-red-700">Could not load data.</p>;

  const pages = Math.max(1, Math.ceil(data.count / 25));
  return (
    <div className={isFetching ? "opacity-70" : ""}>
      <div className="overflow-x-auto rounded border bg-white">
        <table className="w-full text-left text-sm">
          <thead className="bg-slate-50 text-slate-600">
            <tr>{columns.map((c) => <th key={c.key} className="px-3 py-2 font-medium">{c.header}</th>)}</tr>
          </thead>
          <tbody>
            {data.results.length === 0 && (
              <tr><td colSpan={columns.length} className="px-3 py-6 text-center text-slate-500">{empty}</td></tr>
            )}
            {data.results.map((row) => (
              <tr key={row.id} className={`border-t ${onRowClick ? "cursor-pointer hover:bg-slate-50" : ""}`} onClick={() => onRowClick?.(row)}>
                {columns.map((c) => (
                  <td key={c.key} className="px-3 py-2">{c.render ? c.render(row) : String((row as Record<string, unknown>)[c.key] ?? "")}</td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div className="mt-3 flex items-center justify-between text-sm text-slate-600">
        <span>{data.count} total</span>
        <div className="flex items-center gap-2">
          <button className="rounded border px-3 py-1 disabled:opacity-40" disabled={page <= 1} onClick={() => setPage(page - 1)}>Prev</button>
          <span>Page {page} / {pages}</span>
          <button className="rounded border px-3 py-1 disabled:opacity-40" disabled={!data.next} onClick={() => setPage(page + 1)}>Next</button>
        </div>
      </div>
    </div>
  );
}
