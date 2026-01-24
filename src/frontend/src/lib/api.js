/**
 * PilotLog API client
 */

const API_BASE = '/api';

/**
 * Fetch wrapper with error handling
 */
async function fetchApi(endpoint, options = {}) {
  const url = `${API_BASE}${endpoint}`;

  try {
    const response = await fetch(url, {
      headers: {
        'Content-Type': 'application/json',
        ...options.headers,
      },
      ...options,
    });

    if (!response.ok) {
      const error = await response.json().catch(() => ({ detail: 'Unknown error' }));
      throw new Error(error.detail || `HTTP ${response.status}`);
    }

    return await response.json();
  } catch (error) {
    console.error(`API error: ${endpoint}`, error);
    throw error;
  }
}

/**
 * Build query string from params object
 */
function buildQuery(params) {
  const query = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value !== null && value !== undefined && value !== '') {
      query.append(key, value);
    }
  }
  const str = query.toString();
  return str ? `?${str}` : '';
}

/**
 * Get flights with optional filters
 */
export async function getFlights(params = {}) {
  const query = buildQuery(params);
  return fetchApi(`/flights${query}`);
}

/**
 * Get career statistics
 */
export async function getStats(params = {}) {
  const query = buildQuery(params);
  return fetchApi(`/stats${query}`);
}

/**
 * Get rolling totals
 */
export async function getRolling(asOf = null) {
  const query = asOf ? `?as_of=${asOf}` : '';
  return fetchApi(`/rolling${query}`);
}

/**
 * Get route data for map
 */
export async function getRoutes(params = {}) {
  const query = buildQuery(params);
  return fetchApi(`/routes${query}`);
}

/**
 * Get airports list
 */
export async function getAirports() {
  return fetchApi('/airports');
}

/**
 * Import a CSV file
 */
export async function importCsv(file) {
  const formData = new FormData();
  formData.append('file', file);

  const response = await fetch(`${API_BASE}/import`, {
    method: 'POST',
    body: formData,
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Import failed' }));
    throw new Error(error.detail || `HTTP ${response.status}`);
  }

  return await response.json();
}

/**
 * Health check
 */
export async function healthCheck() {
  return fetchApi('/health');
}
