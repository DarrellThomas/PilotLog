<script>
  import { onMount, onDestroy } from 'svelte';
  import {
    mapThemes,
    routeColors,
    getSettings,
    updateSettings,
    subscribeSettings
  } from '../lib/settings.js';

  let settings = $state(getSettings());
  let unsubscribe;

  onMount(() => {
    unsubscribe = subscribeSettings((s) => {
      settings = s;
    });
  });

  onDestroy(() => {
    if (unsubscribe) unsubscribe();
  });

  function handleThemeChange(themeId) {
    updateSettings({ mapTheme: themeId });
  }

  function handleColorChange(colorId) {
    updateSettings({ routeColor: colorId });
  }
</script>

<div class="settings-page">
  <h1>Settings</h1>

  <section class="settings-section">
    <h2>Map Theme</h2>
    <p class="section-desc">Choose how the map background appears</p>
    <div class="option-grid">
      {#each Object.entries(mapThemes) as [id, theme]}
        <button
          class="option-card"
          class:selected={settings.mapTheme === id}
          onclick={() => handleThemeChange(id)}
        >
          <div class="option-preview map-preview {id}"></div>
          <span class="option-label">{theme.name}</span>
        </button>
      {/each}
    </div>
  </section>

  <section class="settings-section">
    <h2>Route Color</h2>
    <p class="section-desc">Choose the color for flight routes on the map</p>
    <div class="option-grid">
      {#each Object.entries(routeColors) as [id, colorOpt]}
        <button
          class="option-card"
          class:selected={settings.routeColor === id}
          onclick={() => handleColorChange(id)}
        >
          <div class="option-preview color-preview" style="background: {colorOpt.color}"></div>
          <span class="option-label">{colorOpt.name}</span>
        </button>
      {/each}
    </div>
  </section>
</div>

<style>
  .settings-page {
    max-width: 800px;
    margin: 0 auto;
  }

  h1 {
    margin-bottom: var(--space-xl);
  }

  .settings-section {
    margin-bottom: var(--space-xl);
  }

  h2 {
    margin-bottom: var(--space-xs);
  }

  .section-desc {
    color: var(--text-muted);
    margin-bottom: var(--space-md);
  }

  .option-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(120px, 1fr));
    gap: var(--space-md);
  }

  .option-card {
    background: var(--bg-secondary);
    border: 2px solid var(--bg-surface);
    border-radius: var(--radius-md);
    padding: var(--space-sm);
    cursor: pointer;
    transition: all 0.2s ease;
    text-align: center;
  }

  .option-card:hover {
    border-color: var(--text-muted);
  }

  .option-card.selected {
    border-color: var(--accent-primary);
    background: var(--bg-surface);
  }

  .option-preview {
    width: 100%;
    height: 60px;
    border-radius: var(--radius-sm);
    margin-bottom: var(--space-sm);
  }

  .map-preview.dark {
    background: linear-gradient(135deg, #1a1a2e 50%, #16213e 50%);
  }

  .map-preview.light {
    background: linear-gradient(135deg, #f5f5f5 50%, #e8e8e8 50%);
  }

  .map-preview.voyager {
    background: linear-gradient(135deg, #f2efe9 50%, #d4cfc5 50%);
  }

  .map-preview.satellite {
    background: linear-gradient(135deg, #2d4a3e 50%, #1a3a2a 50%);
  }

  .map-preview.terrain {
    background: linear-gradient(135deg, #c9d4a5 50%, #a8b88a 50%);
  }

  .map-preview.osm {
    background: linear-gradient(135deg, #f2efe9 50%, #aad3df 50%);
  }

  .color-preview {
    border: 1px solid rgba(255, 255, 255, 0.2);
  }

  .option-label {
    font-size: 0.875rem;
    color: var(--text-primary);
  }
</style>
