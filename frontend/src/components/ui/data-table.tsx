"use client";

"use no memo";

import {
  flexRender,
  getCoreRowModel,
  useReactTable,
  type ColumnDef,
} from "@tanstack/react-table";
import { useRef, type KeyboardEvent } from "react";

type DataTableProps<TData> = {
  columns: ColumnDef<TData>[];
  data: readonly TData[];
  getRowId: (row: TData) => string;
  caption: string;
  selectedRowId?: string;
  onRowSelect?: (row: TData) => void;
  onRowOpen?: (row: TData) => void;
};

export function DataTable<TData>({
  columns,
  data,
  getRowId,
  caption,
  selectedRowId,
  onRowSelect,
  onRowOpen,
}: DataTableProps<TData>) {
  const rowRefs = useRef<Array<HTMLTableRowElement | null>>([]);
  // TanStack Table intentionally owns its internal memoization. Keep this
  // suppression at the adapter boundary; the rule remains active elsewhere.
  // eslint-disable-next-line react-hooks/incompatible-library
  const table = useReactTable({
    columns,
    data: [...data],
    getCoreRowModel: getCoreRowModel(),
    getRowId,
  });

  function handleRowKeyDown(
    event: KeyboardEvent<HTMLTableRowElement>,
    index: number,
    row: TData,
  ) {
    if (!onRowSelect) return;
    if (event.key === "ArrowDown" || event.key === "ArrowUp") {
      event.preventDefault();
      const direction = event.key === "ArrowDown" ? 1 : -1;
      const nextIndex = Math.min(
        table.getRowModel().rows.length - 1,
        Math.max(0, index + direction),
      );
      const nextRow = table.getRowModel().rows[nextIndex];
      rowRefs.current[nextIndex]?.focus();
      if (nextRow) onRowSelect(nextRow.original);
    }
    if (event.key === "Enter" || event.key === " ") {
      event.preventDefault();
      if (event.key === "Enter" && onRowOpen) onRowOpen(row);
      else onRowSelect(row);
    }
  }

  return (
    <div
      role="region"
      aria-label={caption}
      tabIndex={0}
      className="min-h-[360px] max-h-[calc(100vh-320px)] overflow-auto focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus focus-visible:ring-inset"
    >
      <table className="w-full min-w-[920px] table-fixed border-collapse">
        <caption className="sr-only">{caption}</caption>
        <thead className="sticky top-0 z-10 bg-surface-subtle shadow-[0_1px_0_0_var(--color-border)]">
          {table.getHeaderGroups().map((headerGroup) => (
            <tr key={headerGroup.id} className="h-10 border-b border-border">
              {headerGroup.headers.map((header) => (
                <th
                  key={header.id}
                  scope="col"
                  style={{ width: header.getSize() }}
                  className="px-4 text-left text-[11px] font-semibold uppercase tracking-[0.06em] text-muted last:text-right"
                >
                  {header.isPlaceholder
                    ? null
                    : flexRender(header.column.columnDef.header, header.getContext())}
                </th>
              ))}
            </tr>
          ))}
        </thead>
        <tbody className="divide-y divide-border">
          {table.getRowModel().rows.map((row, index) => (
            <tr
              key={row.id}
              ref={(element) => {
                rowRefs.current[index] = element;
              }}
              aria-selected={onRowSelect ? row.id === selectedRowId : undefined}
              tabIndex={onRowSelect ? (row.id === selectedRowId || (!selectedRowId && index === 0) ? 0 : -1) : undefined}
              onClick={onRowOpen ? () => onRowOpen(row.original) : onRowSelect ? () => onRowSelect(row.original) : undefined}
              onKeyDown={onRowSelect ? (event) => handleRowKeyDown(event, index, row.original) : undefined}
              className={`h-16 transition-[background-color,box-shadow] focus-visible:outline-none focus-visible:shadow-[inset_3px_0_0_var(--color-info)] ${onRowSelect ? "cursor-pointer hover:bg-surface-subtle hover:shadow-[inset_2px_0_0_var(--color-info)]" : ""} ${row.id === selectedRowId ? "bg-surface-selected shadow-[inset_3px_0_0_var(--color-info)]" : !onRowSelect && index === 0 ? "bg-surface-selected/50" : "bg-surface"}`}
            >
              {row.getVisibleCells().map((cell) => (
                <td key={cell.id} className="px-4 align-middle last:text-right">
                  {flexRender(cell.column.columnDef.cell, cell.getContext())}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
