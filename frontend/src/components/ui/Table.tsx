import type { HTMLAttributes, TdHTMLAttributes, ThHTMLAttributes } from "react";
import { cn } from "@/lib/cn";

function TableRoot({
  children,
  className,
  ...props
}: HTMLAttributes<HTMLTableElement>) {
  return (
    <div className="w-full overflow-x-auto">
      <table className={cn("w-full border-collapse", className)} {...props}>
        {children}
      </table>
    </div>
  );
}

function Head({
  children,
  className,
  ...props
}: HTMLAttributes<HTMLTableSectionElement>) {
  return (
    <thead className={className} {...props}>
      {children}
    </thead>
  );
}

function Body({
  children,
  className,
  ...props
}: HTMLAttributes<HTMLTableSectionElement>) {
  return (
    <tbody className={className} {...props}>
      {children}
    </tbody>
  );
}

function Row({
  children,
  className,
  ...props
}: HTMLAttributes<HTMLTableRowElement>) {
  return (
    <tr
      className={cn(
        "group border-b border-[var(--color-border-subtle)] hover:bg-[var(--color-layer-hover)] transition-colors",
        className,
      )}
      {...props}
    >
      {children}
    </tr>
  );
}

function HeadCell({
  children,
  className,
  ...props
}: ThHTMLAttributes<HTMLTableCellElement>) {
  return (
    <th
      className={cn(
        "py-2 px-2.5 text-left text-[11px] uppercase tracking-wider font-medium text-[var(--color-text-tertiary)] border-b border-[var(--color-border-default)]",
        className,
      )}
      {...props}
    >
      {children}
    </th>
  );
}

function Cell({
  children,
  className,
  ...props
}: TdHTMLAttributes<HTMLTableCellElement>) {
  return (
    <td className={cn("py-2 px-2.5 text-[13px]", className)} {...props}>
      {children}
    </td>
  );
}

export const Table = Object.assign(TableRoot, {
  Head,
  Body,
  Row,
  HeadCell,
  Cell,
});
