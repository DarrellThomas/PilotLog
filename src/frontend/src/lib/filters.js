/**
 * Shared filter store for synchronizing filters across Map, Flights, and Stats views.
 */

// Calculate default dates (last 3 months)
function getDefaultDates() {
  const today = new Date();
  const threeMonthsAgo = new Date(today);
  threeMonthsAgo.setMonth(threeMonthsAgo.getMonth() - 3);

  return {
    dateFrom: threeMonthsAgo.toISOString().split('T')[0],
    dateTo: today.toISOString().split('T')[0],
  };
}

const defaultFilters = {
  ...getDefaultDates(),
  crew: '',
  tail: '',
  origin: '',
  destination: '',
};

let filters = { ...defaultFilters };
let subscribers = [];

export function getFilters() {
  return { ...filters };
}

export function updateFilters(newFilters) {
  filters = { ...filters, ...newFilters };
  subscribers.forEach(fn => fn(filters));
}

export function resetFilters() {
  filters = { ...defaultFilters };
  subscribers.forEach(fn => fn(filters));
}

export function clearFilters() {
  filters = {
    dateFrom: '',
    dateTo: '',
    crew: '',
    tail: '',
    origin: '',
    destination: '',
  };
  subscribers.forEach(fn => fn(filters));
}

export function subscribeFilters(fn) {
  subscribers.push(fn);
  fn(filters); // Call immediately with current value
  return () => {
    subscribers = subscribers.filter(s => s !== fn);
  };
}

// Helper to build query params from filters
export function buildFilterParams(filters) {
  const params = {};
  if (filters.dateFrom) params.date_from = filters.dateFrom;
  if (filters.dateTo) params.date_to = filters.dateTo;
  if (filters.crew) params.crew = filters.crew;
  if (filters.tail) params.tail = filters.tail;
  if (filters.origin) params.origin = filters.origin;
  if (filters.destination) params.destination = filters.destination;
  return params;
}
