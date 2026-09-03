import * as React from 'react';

interface Column<T> {
  header: string;
  accessor: keyof T;
  sortable?: boolean;
}

export default function DataTable<T extends object>({
  columns,
  data,
  renderActions,
}: {
  columns: Column<T>[];
  data: T[];
  renderActions?: (row: T) => React.ReactNode;
}) {
  const [sortKey, setSortKey] = React.useState<keyof T | null>(null);
  const [sortAsc, setSortAsc] = React.useState(true);

  const sorted = React.useMemo(() => {
    if (!sortKey) return data;
    const copy = [...data];
    copy.sort((a, b) => {
      const av = a[sortKey];
      const bv = b[sortKey];
      if (av === bv) return 0;
      if (av == null) return 1;
      if (bv == null) return -1;
      if (typeof av === 'number' && typeof bv === 'number') {
        return sortAsc ? av - bv : bv - av;
      }
      return sortAsc
        ? String(av).localeCompare(String(bv))
        : String(bv).localeCompare(String(av));
    });
    return copy;
  }, [data, sortKey, sortAsc]);

  const onHeaderClick = (col: Column<T>) => {
    if (!col.sortable) return;
    if (sortKey === col.accessor) {
      setSortAsc(!sortAsc);
    } else {
      setSortKey(col.accessor);
      setSortAsc(true);
    }
  };

  return (
    <div className="overflow-x-auto rounded-lg border border-slate-200 dark:border-gray-700">
      <table className="min-w-full divide-y divide-slate-200 dark:divide-gray-700 text-sm text-slate-600 dark:text-gray-300">
        <thead className="bg-slate-50 dark:bg-gray-800">
          <tr>
            {columns.map((col) => (
              <th
                key={String(col.accessor)}
                className={`px-3 py-2 cursor-${col.sortable ? 'pointer' : 'default'} text-left`}
                onClick={() => onHeaderClick(col)}
              >
                {col.header}
                {col.sortable && sortKey === col.accessor && (
                  <span className="ml-1">{sortAsc ? '▲' : '▼'}</span>
                )}
              </th>
            ))}
            <th className="px-3 py-2 text-left">Actions</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-100 dark:divide-gray-800">
          {sorted.map((row, i) => (
            <tr key={i} className="hover:bg-slate-50 dark:hover:bg-gray-800/30">
              {columns.map((col) => (
                <td key={String(col.accessor)} className="px-3 py-2">
                  {String(row[col.accessor] ?? '-')}
                </td>
              ))}
              <td className="px-3 py-2">
                {renderActions ? renderActions(row) : null}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
