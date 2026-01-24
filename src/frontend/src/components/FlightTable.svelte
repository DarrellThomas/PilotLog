<script>
  import { onMount, onDestroy } from 'svelte';
  import { getFlights } from '../lib/api.js';
  import { getFilters, updateFilters, resetFilters, clearFilters as clearAllFilters, subscribeFilters } from '../lib/filters.js';

  let flights = $state([]);
  let total = $state(0);
  let loading = $state(true);
  let error = $state(null);
  let filters = $state(getFilters());
  let unsubscribeFilters;

  // Pagination
  let limit = $state(50);
  let offset = $state(0);

  onMount(() => {
    unsubscribeFilters = subscribeFilters((newFilters) => {
      filters = newFilters;
    });
    loadFlights();
  });

  onDestroy(() => {
    if (unsubscribeFilters) unsubscribeFilters();
  });

  async function loadFlights() {
    loading = true;
    error = null;

    try {
      const params = { limit, offset };
      if (filters.dateFrom) params.date_from = filters.dateFrom;
      if (filters.dateTo) params.date_to = filters.dateTo;
      if (filters.crew) params.crew = filters.crew;
      if (filters.tail) params.tail = filters.tail;
      if (filters.origin) params.origin = filters.origin;
      if (filters.destination) params.destination = filters.destination;

      const result = await getFlights(params);
      flights = result.flights;
      total = result.total;
    } catch (e) {
      error = e.message;
    } finally {
      loading = false;
    }
  }

  function handleSearch() {
    updateFilters({ ...filters });
    offset = 0;
    loadFlights();
  }

  function handleReset() {
    resetFilters();
    filters = getFilters();
    offset = 0;
    loadFlights();
  }

  function handleClear() {
    clearAllFilters();
    filters = getFilters();
    offset = 0;
    loadFlights();
  }

  function nextPage() {
    if (offset + limit < total) {
      offset += limit;
      loadFlights();
    }
  }

  function prevPage() {
    if (offset > 0) {
      offset = Math.max(0, offset - limit);
      loadFlights();
    }
  }

  let currentPage = $derived(Math.floor(offset / limit) + 1);
  let totalPages = $derived(Math.ceil(total / limit));

  // Calculate totals for current view
  let totalMinutes = $derived(flights.reduce((sum, f) => sum + (f.is_deadhead ? 0 : f.block_minutes), 0));
  let totalFormatted = $derived(`${Math.floor(totalMinutes / 60)}:${String(totalMinutes % 60).padStart(2, '0')}`);
</script>

<div class="flight-table">
  <div class="filters card">
    <div class="filter-row">
      <label>
        <span>Date From</span>
        <input type="date" bind:value={filters.dateFrom} />
      </label>
      <label>
        <span>Date To</span>
        <input type="date" bind:value={filters.dateTo} />
      </label>
      <label>
        <span>Crew</span>
        <input type="text" bind:value={filters.crew} placeholder="Name..." />
      </label>
      <label>
        <span>Tail</span>
        <input type="text" bind:value={filters.tail} placeholder="N12345" />
      </label>
      <label>
        <span>Origin</span>
        <input type="text" bind:value={filters.origin} placeholder="KHOU" />
      </label>
      <label>
        <span>Destination</span>
        <input type="text" bind:value={filters.destination} placeholder="KDEN" />
      </label>
    </div>
    <div class="filter-actions">
      <button class="primary" onclick={handleSearch}>Search</button>
      <button class="secondary" onclick={handleReset}>Reset</button>
      <button class="secondary" onclick={handleClear}>Clear All</button>
    </div>
  </div>

  {#if loading}
    <div class="loading">
      <div class="spinner"></div>
    </div>
  {:else if error}
    <div class="error card">Error: {error}</div>
  {:else}
    <div class="table-container card">
      <table>
        <thead>
          <tr>
            <th>Date</th>
            <th>Flight</th>
            <th>Route</th>
            <th>Block</th>
            <th>Tail</th>
            <th>Type</th>
            <th>Crew</th>
            <th>PIC</th>
          </tr>
        </thead>
        <tbody>
          {#each flights as flight}
            <tr class:deadhead={flight.is_deadhead}>
              <td class="mono">{flight.flight_date}</td>
              <td>{flight.flight_number || '--'}</td>
              <td class="mono">{flight.origin} → {flight.destination}</td>
              <td class="mono">{flight.is_deadhead ? 'DH' : flight.block_formatted}</td>
              <td class="mono">{flight.tail_number || '--'}</td>
              <td>{flight.aircraft_type || '--'}</td>
              <td>{flight.crew_name || '--'}</td>
              <td>
                {#if flight.pic_takeoff && flight.pic_landing}
                  T/L
                {:else if flight.pic_takeoff}
                  T
                {:else if flight.pic_landing}
                  L
                {:else}
                  --
                {/if}
              </td>
            </tr>
          {/each}
        </tbody>
      </table>
    </div>

    <div class="table-footer">
      <div class="summary">
        Showing {offset + 1}-{Math.min(offset + limit, total)} of {total.toLocaleString()} flights
        <span class="total-time">| Block: {totalFormatted}</span>
      </div>
      <div class="pagination">
        <button class="secondary" onclick={prevPage} disabled={offset === 0}>
          ← Prev
        </button>
        <span class="page-info">Page {currentPage} of {totalPages}</span>
        <button class="secondary" onclick={nextPage} disabled={offset + limit >= total}>
          Next →
        </button>
      </div>
    </div>
  {/if}
</div>

<style>
  .flight-table {
    max-width: 1400px;
    margin: 0 auto;
  }

  .filters {
    margin-bottom: var(--space-md);
  }

  .filter-row {
    display: grid;
    grid-template-columns: repeat(6, 1fr);
    gap: var(--space-md);
    margin-bottom: var(--space-md);
  }

  .filter-row label {
    display: flex;
    flex-direction: column;
    gap: var(--space-xs);
  }

  .filter-row label span {
    font-size: 0.75rem;
    color: var(--text-muted);
    text-transform: uppercase;
  }

  .filter-actions {
    display: flex;
    gap: var(--space-sm);
  }

  .loading {
    display: flex;
    justify-content: center;
    padding: var(--space-xl);
  }

  .table-container {
    overflow-x: auto;
    padding: 0;
  }

  table {
    min-width: 900px;
  }

  .deadhead {
    opacity: 0.6;
  }

  .deadhead td {
    font-style: italic;
  }

  .table-footer {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-top: var(--space-md);
    padding: var(--space-md);
    background-color: var(--bg-secondary);
    border-radius: var(--radius-md);
  }

  .summary {
    color: var(--text-muted);
  }

  .total-time {
    font-family: var(--font-mono);
    color: var(--text-primary);
  }

  .pagination {
    display: flex;
    align-items: center;
    gap: var(--space-md);
  }

  .page-info {
    color: var(--text-muted);
  }

  @media (max-width: 1024px) {
    .filter-row {
      grid-template-columns: repeat(3, 1fr);
    }
  }

  @media (max-width: 640px) {
    .filter-row {
      grid-template-columns: 1fr;
    }
  }
</style>
