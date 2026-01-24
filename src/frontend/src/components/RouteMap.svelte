<script>
  import { onMount, onDestroy } from 'svelte';
  import { getRoutes } from '../lib/api.js';
  import { mapThemes, routeColors, getSettings, subscribeSettings } from '../lib/settings.js';
  import { getFilters, updateFilters, resetFilters, clearFilters, subscribeFilters } from '../lib/filters.js';
  import L from 'leaflet';

  let mapContainer;
  let map;
  let tileLayer;
  let loading = true;
  let error = null;
  let routeData = null;
  let selectedRoute = null;
  let settings = getSettings();
  let filters = getFilters();
  let unsubscribeSettings;
  let unsubscribeFilters;

  // Airport coordinates (sample - will be populated from data)
  const airportCoords = {};

  /**
   * Calculate intermediate points along a great circle arc.
   * @param {[number, number]} start - [lat, lng] of origin
   * @param {[number, number]} end - [lat, lng] of destination
   * @param {number} numPoints - number of intermediate points
   * @returns {Array<[number, number]>} array of [lat, lng] points
   */
  function getGreatCirclePoints(start, end, numPoints = 50) {
    const toRad = (deg) => deg * Math.PI / 180;
    const toDeg = (rad) => rad * 180 / Math.PI;

    const lat1 = toRad(start[0]);
    const lng1 = toRad(start[1]);
    const lat2 = toRad(end[0]);
    const lng2 = toRad(end[1]);

    // Calculate angular distance between points
    const d = 2 * Math.asin(Math.sqrt(
      Math.pow(Math.sin((lat1 - lat2) / 2), 2) +
      Math.cos(lat1) * Math.cos(lat2) * Math.pow(Math.sin((lng1 - lng2) / 2), 2)
    ));

    // If points are very close, just return a straight line
    if (d < 0.0001) {
      return [start, end];
    }

    const points = [];

    for (let i = 0; i <= numPoints; i++) {
      const f = i / numPoints;

      // Spherical interpolation
      const A = Math.sin((1 - f) * d) / Math.sin(d);
      const B = Math.sin(f * d) / Math.sin(d);

      const x = A * Math.cos(lat1) * Math.cos(lng1) + B * Math.cos(lat2) * Math.cos(lng2);
      const y = A * Math.cos(lat1) * Math.sin(lng1) + B * Math.cos(lat2) * Math.sin(lng2);
      const z = A * Math.sin(lat1) + B * Math.sin(lat2);

      const lat = Math.atan2(z, Math.sqrt(x * x + y * y));
      const lng = Math.atan2(y, x);

      points.push([toDeg(lat), toDeg(lng)]);
    }

    return points;
  }

  onMount(async () => {
    initMap();

    // Subscribe to settings changes
    unsubscribeSettings = subscribeSettings((newSettings) => {
      const themeChanged = settings.mapTheme !== newSettings.mapTheme;
      const colorChanged = settings.routeColor !== newSettings.routeColor;
      settings = newSettings;

      if (map) {
        if (themeChanged) {
          updateTileLayer();
        }
        if (colorChanged) {
          updateMapLayers();
        }
      }
    });

    // Subscribe to filter changes
    unsubscribeFilters = subscribeFilters((newFilters) => {
      filters = newFilters;
    });

    // Initial data load
    await loadData();
  });

  onDestroy(() => {
    if (unsubscribeSettings) unsubscribeSettings();
    if (unsubscribeFilters) unsubscribeFilters();
    if (map) {
      map.remove();
    }
  });

  function updateTileLayer() {
    if (!map) return;
    const theme = mapThemes[settings.mapTheme] || mapThemes.light;

    if (tileLayer) {
      map.removeLayer(tileLayer);
    }

    tileLayer = L.tileLayer(theme.url, {
      attribution: theme.attribution,
      subdomains: 'abcd',
      maxZoom: 19
    }).addTo(map);
  }

  async function loadData() {
    loading = true;
    error = null;

    try {
      const params = {};
      if (filters.dateFrom) params.date_from = filters.dateFrom;
      if (filters.dateTo) params.date_to = filters.dateTo;
      // Note: routes API currently only supports date filters
      // origin/destination could be added to backend if needed

      routeData = await getRoutes(params);

      // Build airport coords lookup
      for (const airport of routeData.airports) {
        if (airport.latitude && airport.longitude) {
          airportCoords[airport.icao] = [airport.latitude, airport.longitude];
        }
      }

      if (map) {
        updateMapLayers();
      }
    } catch (e) {
      error = e.message;
    } finally {
      loading = false;
    }
  }

  function initMap() {
    // Initialize Leaflet map
    map = L.map(mapContainer, {
      center: [39.8, -98.5], // Center of US
      zoom: 4,
      preferCanvas: true,
    });

    // Add tile layer based on settings
    updateTileLayer();

    if (routeData) {
      updateMapLayers();
    }
  }

  function updateMapLayers() {
    if (!map || !routeData) return;

    // Clear existing layers
    map.eachLayer((layer) => {
      if (layer instanceof L.Polyline || layer instanceof L.CircleMarker) {
        map.removeLayer(layer);
      }
    });

    // Find max count for intensity scaling
    const maxCount = Math.max(...routeData.routes.map(r => r.count), 1);

    // Draw routes as great circle arcs
    for (const route of routeData.routes) {
      const origin = airportCoords[route.origin];
      const dest = airportCoords[route.destination];

      if (!origin || !dest) continue;

      // Calculate intensity (log scale for better distribution)
      const intensity = Math.log10(route.count + 1) / Math.log10(maxCount + 1);
      const weight = 1 + intensity * 3;
      const opacity = 0.2 + intensity * 0.7;

      // Calculate great circle arc points
      // Use more points for longer routes
      const distance = Math.abs(origin[1] - dest[1]) + Math.abs(origin[0] - dest[0]);
      const numPoints = Math.max(20, Math.min(100, Math.round(distance * 2)));
      const arcPoints = getGreatCirclePoints(origin, dest, numPoints);

      const colorOpt = routeColors[settings.routeColor] || routeColors.canyonBlue;
      const line = L.polyline(arcPoints, {
        color: colorOpt.color,
        weight: weight,
        opacity: opacity,
      }).addTo(map);

      line.on('click', () => {
        selectedRoute = route;
      });

      line.bindTooltip(`${route.origin} → ${route.destination}: ${route.count} flights`);
    }

    // Find max visits for scaling airport markers
    const maxVisits = Math.max(...routeData.airports.map(a => a.departures + a.arrivals), 1);

    // Draw airports
    for (const airport of routeData.airports) {
      const coords = airportCoords[airport.icao];
      if (!coords) continue;

      const totalVisits = airport.departures + airport.arrivals;
      // Scale radius based on visits (log scale for better distribution)
      const visitIntensity = Math.log10(totalVisits + 1) / Math.log10(maxVisits + 1);
      const radius = 3 + visitIntensity * 10;

      const airportColorOpt = routeColors[settings.routeColor] || routeColors.canyonBlue;
      L.circleMarker(coords, {
        radius: radius,
        fillColor: airportColorOpt.light,
        fillOpacity: 0.7 + visitIntensity * 0.25,
        color: '#fff',
        weight: 1,
      })
        .bindTooltip(`${airport.icao}${airport.name ? ': ' + airport.name : ''}<br>${totalVisits} visits`)
        .addTo(map);
    }
  }

  function handleFilter() {
    updateFilters({
      dateFrom: filters.dateFrom,
      dateTo: filters.dateTo,
      origin: filters.origin,
      destination: filters.destination,
    });
    loadData();
  }

  function handleReset() {
    resetFilters();
    filters = getFilters();
    loadData();
  }

  function handleClear() {
    clearFilters();
    filters = getFilters();
    loadData();
  }
</script>

<div class="route-map">
  <div class="controls">
    <div class="filter-group">
      <label>
        From:
        <input type="date" bind:value={filters.dateFrom} />
      </label>
      <label>
        To:
        <input type="date" bind:value={filters.dateTo} />
      </label>
      <label>
        Origin:
        <input type="text" bind:value={filters.origin} placeholder="ICAO" />
      </label>
      <label>
        Destination:
        <input type="text" bind:value={filters.destination} placeholder="ICAO" />
      </label>
      <button class="primary" onclick={handleFilter}>Apply</button>
      <button class="secondary" onclick={handleReset}>Reset</button>
      <button class="secondary" onclick={handleClear}>Clear All</button>
    </div>
  </div>

  <div class="map-container" bind:this={mapContainer}>
    {#if loading}
      <div class="map-loading">
        <div class="spinner"></div>
      </div>
    {/if}
  </div>

  {#if selectedRoute}
    <div class="route-info card">
      <button class="close-btn" onclick={() => selectedRoute = null}>×</button>
      <h3>{selectedRoute.origin} → {selectedRoute.destination}</h3>
      <div class="info-grid">
        <div>
          <span class="label">Flights</span>
          <span class="value">{selectedRoute.count}</span>
        </div>
        <div>
          <span class="label">Total Time</span>
          <span class="value mono">
            {Math.floor(selectedRoute.total_minutes / 60)}:{String(selectedRoute.total_minutes % 60).padStart(2, '0')}
          </span>
        </div>
        <div>
          <span class="label">First Flown</span>
          <span class="value">{selectedRoute.first_flown || '--'}</span>
        </div>
        <div>
          <span class="label">Last Flown</span>
          <span class="value">{selectedRoute.last_flown || '--'}</span>
        </div>
      </div>
    </div>
  {/if}

  {#if error}
    <div class="error-toast">Error: {error}</div>
  {/if}
</div>

<style>
  .route-map {
    height: 100%;
    display: flex;
    flex-direction: column;
    position: relative;
  }

  .controls {
    margin-bottom: var(--space-md);
  }

  .filter-group {
    display: flex;
    gap: var(--space-md);
    align-items: end;
  }

  .filter-group label {
    display: flex;
    flex-direction: column;
    gap: var(--space-xs);
    font-size: 0.875rem;
    color: var(--text-muted);
  }

  .map-container {
    flex: 1;
    border-radius: var(--radius-md);
    overflow: hidden;
    position: relative;
    min-height: 400px;
  }

  .map-loading {
    position: absolute;
    top: 50%;
    left: 50%;
    transform: translate(-50%, -50%);
    z-index: 1000;
  }

  .route-info {
    position: absolute;
    bottom: var(--space-lg);
    left: var(--space-lg);
    max-width: 300px;
    z-index: 1000;
  }

  .route-info h3 {
    font-family: var(--font-mono);
    margin-bottom: var(--space-md);
  }

  .close-btn {
    position: absolute;
    top: var(--space-sm);
    right: var(--space-sm);
    background: transparent;
    color: var(--text-muted);
    font-size: 1.25rem;
    padding: 0;
    width: 24px;
    height: 24px;
    display: flex;
    align-items: center;
    justify-content: center;
  }

  .close-btn:hover {
    color: var(--text-primary);
  }

  .info-grid {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: var(--space-md);
  }

  .info-grid .label {
    display: block;
    font-size: 0.75rem;
    color: var(--text-muted);
    text-transform: uppercase;
  }

  .info-grid .value {
    font-size: 1rem;
    font-weight: 600;
  }

  .error-toast {
    position: absolute;
    bottom: var(--space-lg);
    right: var(--space-lg);
    background: var(--danger);
    color: white;
    padding: var(--space-sm) var(--space-md);
    border-radius: var(--radius-sm);
    z-index: 1000;
  }
</style>
