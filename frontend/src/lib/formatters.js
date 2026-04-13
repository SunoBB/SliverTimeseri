export function formatNumber(value, options = {}) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) {
    return "--";
  }

  return new Intl.NumberFormat("en-US", options).format(Number(value));
}

export function formatSignedNumber(value, options = {}) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) {
    return "--";
  }

  const number = Number(value);
  const formatted = new Intl.NumberFormat("en-US", options).format(Math.abs(number));
  return `${number >= 0 ? "+" : "-"}${formatted}`;
}
