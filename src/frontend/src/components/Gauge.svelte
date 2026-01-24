<script>
  export let value = 0;
  export let showLabel = false;

  $: percentage = Math.min(Math.max(value, 0), 100);
  $: isDanger = percentage > 85;
</script>

<div class="gauge-container">
  <div class="gauge">
    <div
      class="gauge-fill"
      class:danger={isDanger}
      style="width: {percentage}%"
    ></div>
  </div>
  {#if showLabel}
    <span class="gauge-label">{percentage.toFixed(0)}%</span>
  {/if}
</div>

<style>
  .gauge-container {
    display: flex;
    align-items: center;
    gap: var(--space-sm);
    margin-top: var(--space-sm);
  }

  .gauge {
    flex: 1;
    background-color: var(--bg-surface);
    border-radius: var(--radius-sm);
    height: 8px;
    overflow: hidden;
  }

  .gauge-fill {
    height: 100%;
    background: linear-gradient(90deg, var(--success), var(--warning));
    transition: width 0.3s ease;
    border-radius: var(--radius-sm);
  }

  .gauge-fill.danger {
    background: linear-gradient(90deg, var(--warning), var(--danger));
  }

  .gauge-label {
    font-size: 0.75rem;
    color: var(--text-muted);
    min-width: 3rem;
    text-align: right;
  }
</style>
