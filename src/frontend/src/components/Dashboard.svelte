<script>
  import { onMount } from 'svelte';
  import { getRolling, getStats } from '../lib/api.js';
  import Gauge from './Gauge.svelte';

  let rolling = null;
  let stats = null;
  let loading = true;
  let error = null;

  onMount(async () => {
    try {
      [rolling, stats] = await Promise.all([
        getRolling(),
        getStats()
      ]);
    } catch (e) {
      error = e.message;
    } finally {
      loading = false;
    }
  });

  // FAR 117 limits in hours (only 672-hour and 365-day have actual limits)
  const limits = {
    28: 100,   // 672-hour (28 day) limit
    365: 1000
  };

  // Window labels (672 hours = 28 days)
  const windowLabels = {
    7: '7-Day',
    28: '672-Hour',
    60: '60-Day',
    90: '90-Day',
    365: '365-Day'
  };

  function getWindowData(windowDays) {
    if (!rolling?.windows) return null;
    const data = rolling.windows[String(windowDays)];
    if (!data) return null;

    const hours = data.minutes / 60;
    const limit = limits[windowDays] || 0;
    const percentage = limit > 0 ? (hours / limit) * 100 : 0;
    const nearLimit = limit > 0 && percentage >= 95;

    return {
      ...data,
      hours: hours.toFixed(1),
      limit,
      label: windowLabels[windowDays] || `${windowDays}-Day`,
      percentage: Math.min(percentage, 100),
      nearLimit
    };
  }
</script>

<div class="dashboard">
  {#if loading}
    <div class="loading">
      <div class="spinner"></div>
    </div>
  {:else if error}
    <div class="error card">
      <p>Error loading data: {error}</p>
    </div>
  {:else}
    <section class="rolling-section">
      <h2>Rolling Totals</h2>
      <p class="subtitle">As of {rolling?.as_of || 'today'}</p>

      <div class="grid grid-4">
        {#each [7, 28, 60, 90] as days}
          {@const data = getWindowData(days)}
          <div class="card gauge-card">
            <div class="card-header">{data?.label || windowLabels[days]}</div>
            {#if data}
              <div class="stat-value mono" class:near-limit={data.nearLimit}>{data.formatted}</div>
              <div class="stat-label">{data.flights} flights</div>
              {#if limits[days]}
                <Gauge value={data.percentage} />
                <div class="limit-text" class:near-limit={data.nearLimit}>{data.hours}h / {data.limit}h limit</div>
              {/if}
            {:else}
              <div class="stat-value mono">--:--</div>
            {/if}
          </div>
        {/each}
      </div>

      <div class="grid grid-2">
        <div class="card">
          <div class="card-header">365-Day Lookback</div>
          {#if getWindowData(365)}
            {@const yearData = getWindowData(365)}
            <div class="stat-value mono large" class:near-limit={yearData.nearLimit}>{yearData.formatted}</div>
            <div class="stat-label">{yearData.flights} flights</div>
            <Gauge value={yearData.percentage} />
            <div class="limit-text" class:near-limit={yearData.nearLimit}>{yearData.hours}h / {yearData.limit}h limit</div>
          {/if}
        </div>

        <div class="card">
          <div class="card-header">Career Total</div>
          {#if stats}
            <div class="stat-value mono large">{stats.total_block_formatted}</div>
            <div class="stat-label">{stats.total_flights.toLocaleString()} flights</div>
          {/if}
        </div>
      </div>
    </section>

    <section class="quick-stats">
      <h2>Quick Stats</h2>
      <div class="grid grid-4">
        <div class="card">
          <div class="card-header">Airports</div>
          <div class="stat-value">{stats?.unique_airports || 0}</div>
          <div class="stat-label">unique airports</div>
        </div>
        <div class="card">
          <div class="card-header">Aircraft</div>
          <div class="stat-value">{stats?.unique_aircraft || 0}</div>
          <div class="stat-label">unique tails</div>
        </div>
        <div class="card">
          <div class="card-header">First Flight</div>
          <div class="stat-value mono">{stats?.date_range?.first_flight || '--'}</div>
          <div class="stat-label">career start</div>
        </div>
        <div class="card">
          <div class="card-header">Last Flight</div>
          <div class="stat-value mono">{stats?.date_range?.last_flight || '--'}</div>
          <div class="stat-label">most recent</div>
        </div>
      </div>
    </section>
  {/if}
</div>

<style>
  .dashboard {
    max-width: 1200px;
    margin: 0 auto;
  }

  .loading {
    display: flex;
    justify-content: center;
    padding: var(--space-xl);
  }

  .error {
    color: var(--danger);
  }

  section {
    margin-bottom: var(--space-xl);
  }

  h2 {
    margin-bottom: var(--space-sm);
  }

  .subtitle {
    color: var(--text-muted);
    margin-bottom: var(--space-lg);
  }

  .gauge-card {
    text-align: center;
  }

  .stat-value.large {
    font-size: 2rem;
  }

  .stat-value.near-limit {
    color: #e74c3c;
    font-size: 1.3em;
    font-weight: 700;
  }

  .stat-value.large.near-limit {
    font-size: 2.4rem;
  }

  .limit-text.near-limit {
    color: #e74c3c;
    font-size: 0.9rem;
    font-weight: 600;
  }

  .limit-text {
    font-size: 0.75rem;
    color: var(--text-muted);
    margin-top: var(--space-sm);
  }
</style>
