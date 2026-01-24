<script>
  import Dashboard from './components/Dashboard.svelte';
  import RouteMap from './components/RouteMap.svelte';
  import FlightTable from './components/FlightTable.svelte';
  import Stats from './components/Stats.svelte';
  import Settings from './components/Settings.svelte';
  import ImportModal from './components/ImportModal.svelte';

  let currentView = 'dashboard';
  let showImport = false;

  const views = [
    { id: 'dashboard', label: 'Dashboard' },
    { id: 'map', label: 'Map' },
    { id: 'flights', label: 'Flights' },
    { id: 'stats', label: 'Stats' },
    { id: 'settings', label: 'Settings' },
  ];
</script>

<div class="app">
  <header class="header">
    <div class="header-left">
      <h1 class="logo">PilotLog</h1>
    </div>
    <nav class="nav">
      {#each views as view}
        <button
          class="nav-item"
          class:active={currentView === view.id}
          onclick={() => currentView = view.id}
        >
          {view.label}
        </button>
      {/each}
    </nav>
    <div class="header-right">
      <button class="primary" onclick={() => showImport = true}>
        Import
      </button>
    </div>
  </header>

  <main class="main">
    {#if currentView === 'dashboard'}
      <Dashboard />
    {:else if currentView === 'map'}
      <RouteMap />
    {:else if currentView === 'flights'}
      <FlightTable />
    {:else if currentView === 'stats'}
      <Stats />
    {:else if currentView === 'settings'}
      <Settings />
    {/if}
  </main>

  {#if showImport}
    <ImportModal onclose={() => showImport = false} />
  {/if}
</div>

<style>
  .app {
    height: 100%;
    display: flex;
    flex-direction: column;
  }

  .header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: var(--space-md) var(--space-lg);
    background-color: var(--bg-secondary);
    border-bottom: 1px solid var(--bg-surface);
  }

  .header-left, .header-right {
    flex: 0 0 auto;
  }

  .logo {
    font-size: 1.25rem;
    font-weight: 700;
    margin: 0;
    color: var(--accent-primary);
  }

  .nav {
    display: flex;
    gap: var(--space-sm);
    background: transparent;
    padding: 0;
  }

  .main {
    flex: 1;
    overflow: auto;
    padding: var(--space-lg);
  }
</style>
