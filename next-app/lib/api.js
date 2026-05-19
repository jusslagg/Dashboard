export const API_BASE = process.env.NEXT_PUBLIC_API_BASE || 'http://127.0.0.1:8009';

export async function getJson(path, params) {
  const url = new URL(path, API_BASE);
  if (params) {
    Object.entries(params).forEach(([key, value]) => {
      if (Array.isArray(value)) {
        value.forEach((item) => item && url.searchParams.append(key, item));
      } else if (value !== undefined && value !== null && value !== '') {
        url.searchParams.set(key, value);
      }
    });
  }

  const response = await fetch(url, {
    credentials: 'include',
    cache: 'no-store',
  });

  const contentType = response.headers.get('content-type') || '';
  if (!contentType.includes('application/json')) {
    throw new Error(response.status === 403
      ? 'Sesion expirada o sin permisos. Inicia sesion en Flask y recarga Next.'
      : `Respuesta inesperada del servidor (${response.status}).`);
  }

  const data = await response.json();
  if (!response.ok || data.success === false) {
    throw new Error((data.errores || [`Error ${response.status}`]).join(', '));
  }
  return data;
}

export function formatMoney(value) {
  const number = Number(value || 0);
  const sign = number < 0 ? '-$' : '$';
  return sign + Math.abs(number).toLocaleString('es-AR', {
    minimumFractionDigits: 0,
    maximumFractionDigits: 0,
  });
}

export function formatMoneyFull(value) {
  const number = Number(value || 0);
  const sign = number < 0 ? '-$' : '$';
  return sign + Math.abs(number).toLocaleString('es-AR', {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });
}

export function formatNumber(value, digits = 1) {
  return Number(value || 0).toLocaleString('es-AR', {
    minimumFractionDigits: 0,
    maximumFractionDigits: digits,
  });
}

export function formatPercent(value) {
  return `${Number(value || 0).toLocaleString('es-AR', {
    minimumFractionDigits: 1,
    maximumFractionDigits: 1,
  })}%`;
}

export function formatMonth(month) {
  if (!month || !month.includes('-')) return month || '';
  const [year, rawMonth] = month.split('-');
  const labels = ['ene', 'feb', 'mar', 'abr', 'may', 'jun', 'jul', 'ago', 'sep', 'oct', 'nov', 'dic'];
  return `${labels[Number(rawMonth) - 1] || rawMonth}-${String(year).slice(-2)}`;
}
