export type ReleaseCsvEntry = {
  id: number; admin_id: number; admin_username: string; booking_id: number;
  username: string; vehicle: string; space: string; released_at: string;
  reason?: string; amount_cents: number;
};

function csvCell(value: string | number): string {
  let text = String(value);
  // CSV quoting alone does not prevent spreadsheet formula execution.
  // Prefix dangerous text with an apostrophe before RFC-style escaping.
  if (/^[\s\u0000-\u001f]*[=+\-@]|^[\t\r\n]/.test(text)) text = "'" + text;
  return '"' + text.replace(/"/g, '""') + '"';
}

export function buildReleaseCsv(entries: readonly ReleaseCsvEntry[]): string {
  const rows: (string | number)[][] = [
    ['Audit ID', 'Admin', 'Admin ID', 'Booking ID', 'Released at (ISO 8601)',
      'Reason', 'Booking username', 'Vehicle', 'Space', 'Amount (INR)'],
    ...entries.map(entry => [
      entry.id, entry.admin_username, entry.admin_id, entry.booking_id,
      entry.released_at, entry.reason || 'Not recorded (older entry)',
      entry.username, entry.vehicle, entry.space, (entry.amount_cents / 100).toFixed(2),
    ]),
  ];
  // UTF-8 BOM helps Excel recognize non-English usernames and reasons.
  return '\uFEFF' + rows.map(row => row.map(csvCell).join(',')).join('\r\n') + '\r\n';
}
