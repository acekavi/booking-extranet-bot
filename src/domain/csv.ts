/** Minimal RFC 4180-style CSV, enough for booking exports and run journals. */

export function escapeCsv(value: string): string {
  return /[",\r\n]/.test(value) ? `"${value.replace(/"/g, '""')}"` : value;
}

export function toCsv(headers: string[], rows: string[][]): string {
  return [headers, ...rows].map((row) => row.map(escapeCsv).join(",")).join("\n") + "\n";
}

/**
 * Parse the whole document at once, tracking quote state across it rather than
 * line by line, so a newline inside a quoted field stays data instead of
 * becoming a record separator. Splitting on "\n" first is the usual bug here.
 */
export function parseCsv(text: string): string[][] {
  const rows: string[][] = [];
  let row: string[] = [];
  let field = "";
  let inQuotes = false;

  for (let i = 0; i < text.length; i++) {
    const char = text[i];
    if (inQuotes) {
      if (char === '"') {
        if (text[i + 1] === '"') {
          field += '"';
          i++;
        } else {
          inQuotes = false;
        }
      } else {
        field += char;
      }
    } else if (char === '"') {
      inQuotes = true;
    } else if (char === ",") {
      row.push(field);
      field = "";
    } else if (char === "\n" || char === "\r") {
      // Treat CRLF as one separator, not two.
      if (char === "\r" && text[i + 1] === "\n") i++;
      row.push(field);
      rows.push(row);
      row = [];
      field = "";
    } else {
      field += char;
    }
  }
  if (field !== "" || row.length > 0) {
    row.push(field);
    rows.push(row);
  }
  return rows;
}

/** Parse with a header row into objects keyed by column name. */
export function parseCsvRecords(text: string): Record<string, string>[] {
  const [headers, ...rows] = parseCsv(text);
  if (!headers) return [];
  return rows
    .filter((row) => !(row.length === 1 && row[0] === ""))
    .map((row) => Object.fromEntries(headers.map((h, i) => [h, row[i] ?? ""])));
}
