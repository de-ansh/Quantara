/**
 * Utility for exporting tabular datasets to CSV files in the browser.
 */

export interface CsvColumn {
    key: string
    label: string
}

export function exportToCsv(
    filename: string,
    rows: Record<string, unknown>[],
    columns?: CsvColumn[]
): void {
    if (!rows || rows.length === 0) {
        return
    }

    const cols: CsvColumn[] = columns || Object.keys(rows[0]).map((key) => ({
        key,
        label: key.toUpperCase().replace(/_/g, " ")
    }))

    const headerLine = cols.map((c) => `"${c.label.replace(/"/g, '""')}"`).join(",")

    const dataLines = rows.map((row) => {
        return cols
            .map((c) => {
                const rawVal = row[c.key]
                const val = rawVal === null || rawVal === undefined ? "" : String(rawVal)
                return `"${val.replace(/"/g, '""')}"`
            })
            .join(",")
    })

    const csvContent = [headerLine, ...dataLines].join("\r\n")
    const blob = new Blob([csvContent], { type: "text/csv;charset=utf-8;" })
    const url = URL.createObjectURL(blob)

    const link = document.createElement("a")
    link.href = url
    link.setAttribute("download", filename.endsWith(".csv") ? filename : `${filename}.csv`)
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
    URL.revokeObjectURL(url)
}
