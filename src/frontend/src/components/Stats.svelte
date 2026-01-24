<script>
  import { onMount, onDestroy } from 'svelte';
  import { getStats } from '../lib/api.js';
  import { getFilters, updateFilters, resetFilters, clearFilters, subscribeFilters } from '../lib/filters.js';

  let stats = $state(null);
  let loading = $state(true);
  let error = $state(null);
  let filters = $state(getFilters());
  let unsubscribeFilters;

  onMount(async () => {
    unsubscribeFilters = subscribeFilters((newFilters) => {
      filters = newFilters;
    });
    await loadStats();
  });

  onDestroy(() => {
    if (unsubscribeFilters) unsubscribeFilters();
  });

  async function loadStats() {
    loading = true;
    error = null;
    try {
      const params = {};
      if (filters.dateFrom) params.date_from = filters.dateFrom;
      if (filters.dateTo) params.date_to = filters.dateTo;
      stats = await getStats(params);
    } catch (e) {
      error = e.message;
    } finally {
      loading = false;
    }
  }

  function handleFilter() {
    updateFilters({
      dateFrom: filters.dateFrom,
      dateTo: filters.dateTo,
    });
    loadStats();
  }

  function handleReset() {
    resetFilters();
    filters = getFilters();
    loadStats();
  }

  function handleClear() {
    clearFilters();
    filters = getFilters();
    loadStats();
  }

  function formatMinutes(minutes) {
    const hours = Math.floor(minutes / 60);
    const mins = minutes % 60;
    return `${hours}:${String(mins).padStart(2, '0')}`;
  }
</script>

<div class="stats-page">
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
      <button class="primary" onclick={handleFilter}>Apply</button>
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
  {:else if stats}
    <section class="overview">
      <h2>Career Overview</h2>
      <div class="grid grid-4">
        <div class="card stat-card">
          <div class="stat-value mono">{stats.total_block_formatted}</div>
          <div class="stat-label">Total Block Time</div>
        </div>
        <div class="card stat-card">
          <div class="stat-value">{stats.total_flights.toLocaleString()}</div>
          <div class="stat-label">Total Flights</div>
        </div>
        <div class="card stat-card">
          <div class="stat-value">{stats.unique_airports}</div>
          <div class="stat-label">Airports Visited</div>
        </div>
        <div class="card stat-card">
          <div class="stat-value">{stats.unique_aircraft}</div>
          <div class="stat-label">Unique Aircraft</div>
        </div>
      </div>
    </section>

    <div class="grid grid-2">
      <section class="by-aircraft">
        <h2>By Aircraft Type</h2>
        <div class="card">
          <table>
            <thead>
              <tr>
                <th>Type</th>
                <th class="right">Flights</th>
                <th class="right">Block Time</th>
              </tr>
            </thead>
            <tbody>
              {#each stats.by_aircraft_type as type}
                <tr>
                  <td>{type.type}</td>
                  <td class="right">{type.flights.toLocaleString()}</td>
                  <td class="right mono">{formatMinutes(type.minutes)}</td>
                </tr>
              {/each}
            </tbody>
          </table>
        </div>
      </section>

      <section class="by-year">
        <h2>By Year</h2>
        <div class="card">
          <table>
            <thead>
              <tr>
                <th>Year</th>
                <th class="right">Flights</th>
                <th class="right">Block Time</th>
              </tr>
            </thead>
            <tbody>
              {#each stats.by_year as year}
                <tr>
                  <td>{year.year}</td>
                  <td class="right">{year.flights.toLocaleString()}</td>
                  <td class="right mono">{formatMinutes(year.minutes)}</td>
                </tr>
              {/each}
            </tbody>
          </table>
        </div>
      </section>
    </div>

    <section class="timeline">
      <h2>Year-over-Year</h2>
      <div class="card">
        <div class="chart">
          {#each stats.by_year as year}
            {@const maxMinutes = Math.max(...stats.by_year.map(y => y.minutes))}
            {@const percentage = (year.minutes / maxMinutes) * 100}
            <div class="bar-row">
              <span class="bar-label">{year.year}</span>
              <div class="bar-container">
                <div class="bar" style="width: {percentage}%">
                  <span class="bar-value">{formatMinutes(year.minutes)}</span>
                </div>
              </div>
            </div>
          {/each}
        </div>
      </div>
    </section>
  {/if}
</div>

<style>
  .stats-page {
    max-width: 1200px;
    margin: 0 auto;
  }

  .controls {
    margin-bottom: var(--space-lg);
  }

  .filter-group {
    display: flex;
    gap: var(--space-md);
    align-items: end;
    flex-wrap: wrap;
  }

  .filter-group label {
    display: flex;
    flex-direction: column;
    gap: var(--space-xs);
    font-size: 0.875rem;
    color: var(--text-muted);
  }

  .loading {
    display: flex;
    justify-content: center;
    padding: var(--space-xl);
  }

  section {
    margin-bottom: var(--space-xl);
  }

  h2 {
    margin-bottom: var(--space-md);
  }

  .stat-card {
    text-align: center;
  }

  .stat-card .stat-value {
    font-size: 2rem;
  }

  .right {
    text-align: right;
  }

  /* Bar chart */
  .chart {
    display: flex;
    flex-direction: column;
    gap: var(--space-sm);
  }

  .bar-row {
    display: flex;
    align-items: center;
    gap: var(--space-md);
  }

  .bar-label {
    width: 50px;
    font-family: var(--font-mono);
    font-size: 0.875rem;
    color: var(--text-muted);
  }

  .bar-container {
    flex: 1;
    background-color: var(--bg-surface);
    border-radius: var(--radius-sm);
    height: 24px;
  }

  .bar {
    height: 100%;
    background: linear-gradient(90deg, var(--accent-primary), var(--accent-secondary));
    border-radius: var(--radius-sm);
    display: flex;
    align-items: center;
    justify-content: flex-end;
    padding-right: var(--space-sm);
    min-width: fit-content;
    transition: width 0.3s ease;
  }

  .bar-value {
    font-family: var(--font-mono);
    font-size: 0.75rem;
    color: white;
    white-space: nowrap;
  }
</style>
