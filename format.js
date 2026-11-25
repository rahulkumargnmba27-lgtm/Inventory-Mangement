export function formatINR(amount) {
  const num = Number(amount || 0);
  return new Intl.NumberFormat('en-IN', {
    style: 'currency',
    currency: 'INR',
    maximumFractionDigits: num % 1 === 0 ? 0 : 2,
  }).format(num);
}

export function formatIndianDate(isoStr) {
  if (!isoStr) return '—';
  const d = new Date(isoStr);
  return new Intl.DateTimeFormat('en-IN', {
    day: '2-digit',
    month: 'short',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
    hour12: true,
    timeZone: 'Asia/Kolkata',
  }).format(d);
}

export function formatShortDate(isoStr) {
  if (!isoStr) return '—';
  const d = new Date(isoStr);
  return new Intl.DateTimeFormat('en-IN', {
    day: '2-digit',
    month: 'short',
    year: 'numeric',
    timeZone: 'Asia/Kolkata',
  }).format(d);
}

export function statusBadgeStyle(status) {
  switch (status) {
    case 'HEALTHY':
    case 'CONFIRMED':
    case 'DELIVERED':
    case 'RESOLVED':
      return 'bg-primary-fixed/50 text-on-primary-fixed-variant';
    case 'LOW_STOCK':
    case 'DRAFT':
    case 'ACKNOWLEDGED':
      return 'bg-secondary-fixed text-on-secondary-fixed-variant';
    case 'STOCKOUT':
    case 'CANCELLED':
    case 'ACTIVE':
      return 'bg-tertiary-fixed text-tertiary';
    case 'SAMPLE':
      return 'bg-surface-container-high text-outline';
    default:
      return 'bg-surface-container-high text-on-surface-variant';
  }
}
