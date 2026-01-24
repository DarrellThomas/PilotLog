<script>
  import { importCsv } from '../lib/api.js';

  let { onclose } = $props();

  let file = $state(null);
  let loading = $state(false);
  let error = $state(null);
  let result = $state(null);

  function handleFileSelect(event) {
    file = event.target.files[0];
    error = null;
    result = null;
  }

  async function handleImport() {
    if (!file) {
      error = 'Please select a file';
      return;
    }

    loading = true;
    error = null;

    try {
      result = await importCsv(file);
    } catch (e) {
      error = e.message;
    } finally {
      loading = false;
    }
  }

  function close() {
    onclose?.();
  }

  function handleBackdropClick(event) {
    if (event.target === event.currentTarget) {
      close();
    }
  }
</script>

<div class="modal-backdrop" onclick={handleBackdropClick} role="button" tabindex="-1" onkeydown={(e) => e.key === 'Escape' && close()}>
  <div class="modal">
    <div class="modal-header">
      <h2>Import CSV</h2>
      <button class="close-btn" onclick={close}>×</button>
    </div>

    <div class="modal-body">
      {#if !result}
        <div class="file-input-wrapper">
          <input
            type="file"
            accept=".csv"
            onchange={handleFileSelect}
            id="csv-file"
          />
          <label for="csv-file" class="file-label">
            {file ? file.name : 'Choose a CSV file...'}
          </label>
        </div>

        {#if error}
          <div class="error-message">{error}</div>
        {/if}

        <button
          class="primary import-btn"
          onclick={handleImport}
          disabled={!file || loading}
        >
          {loading ? 'Importing...' : 'Import'}
        </button>
      {:else}
        <div class="result">
          <div class="result-header" class:success={result.rows_imported > 0}>
            {#if result.rows_imported > 0}
              <span class="icon">✓</span> Import Successful
            {:else}
              <span class="icon">!</span> No New Flights
            {/if}
          </div>

          <div class="result-stats">
            <div class="stat-row">
              <span>File:</span>
              <span class="mono">{result.filename}</span>
            </div>
            <div class="stat-row">
              <span>Rows Processed:</span>
              <span>{result.rows_processed}</span>
            </div>
            <div class="stat-row">
              <span>Flights Imported:</span>
              <span class="success">{result.rows_imported}</span>
            </div>
            {#if result.rows_duplicate > 0}
              <div class="stat-row">
                <span>Duplicates Skipped:</span>
                <span class="warning">{result.rows_duplicate}</span>
              </div>
            {/if}
            {#if result.rows_skipped > 0}
              <div class="stat-row">
                <span>Rows Skipped:</span>
                <span class="danger">{result.rows_skipped}</span>
              </div>
            {/if}
            {#if result.summary.new_block_formatted}
              <div class="stat-row">
                <span>New Block Time:</span>
                <span class="mono">{result.summary.new_block_formatted}</span>
              </div>
            {/if}
            {#if result.summary.date_range}
              <div class="stat-row">
                <span>Date Range:</span>
                <span class="mono">{result.summary.date_range}</span>
              </div>
            {/if}
          </div>

          {#if result.errors.length > 0}
            <div class="errors">
              <h4>Errors:</h4>
              <ul>
                {#each result.errors.slice(0, 5) as err}
                  <li>Row {err.row}: {err.message}</li>
                {/each}
                {#if result.errors.length > 5}
                  <li>...and {result.errors.length - 5} more</li>
                {/if}
              </ul>
            </div>
          {/if}

          <button class="secondary" onclick={close}>Close</button>
        </div>
      {/if}
    </div>
  </div>
</div>

<style>
  .modal-backdrop {
    position: fixed;
    top: 0;
    left: 0;
    right: 0;
    bottom: 0;
    background-color: rgba(0, 0, 0, 0.7);
    display: flex;
    align-items: center;
    justify-content: center;
    z-index: 1000;
  }

  .modal {
    background-color: var(--bg-secondary);
    border-radius: var(--radius-lg);
    width: 100%;
    max-width: 480px;
    max-height: 90vh;
    overflow: auto;
  }

  .modal-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: var(--space-lg);
    border-bottom: 1px solid var(--bg-surface);
  }

  .modal-header h2 {
    margin: 0;
  }

  .close-btn {
    background: transparent;
    color: var(--text-muted);
    font-size: 1.5rem;
    padding: 0;
    width: 32px;
    height: 32px;
    display: flex;
    align-items: center;
    justify-content: center;
  }

  .close-btn:hover {
    color: var(--text-primary);
  }

  .modal-body {
    padding: var(--space-lg);
  }

  .file-input-wrapper {
    margin-bottom: var(--space-lg);
  }

  .file-input-wrapper input {
    display: none;
  }

  .file-label {
    display: block;
    padding: var(--space-lg);
    border: 2px dashed var(--bg-surface);
    border-radius: var(--radius-md);
    text-align: center;
    cursor: pointer;
    color: var(--text-muted);
    transition: all 0.2s ease;
  }

  .file-label:hover {
    border-color: var(--accent-primary);
    color: var(--text-primary);
  }

  .error-message {
    color: var(--danger);
    margin-bottom: var(--space-md);
    padding: var(--space-sm) var(--space-md);
    background-color: rgba(214, 48, 49, 0.1);
    border-radius: var(--radius-sm);
  }

  .import-btn {
    width: 100%;
  }

  .result-header {
    font-size: 1.25rem;
    font-weight: 600;
    margin-bottom: var(--space-lg);
    padding: var(--space-md);
    background-color: var(--bg-surface);
    border-radius: var(--radius-md);
    display: flex;
    align-items: center;
    gap: var(--space-sm);
  }

  .result-header.success .icon {
    color: var(--success);
  }

  .result-stats {
    margin-bottom: var(--space-lg);
  }

  .stat-row {
    display: flex;
    justify-content: space-between;
    padding: var(--space-sm) 0;
    border-bottom: 1px solid var(--bg-surface);
  }

  .success { color: var(--success); }
  .warning { color: var(--warning); }
  .danger { color: var(--danger); }

  .errors {
    margin-bottom: var(--space-lg);
    padding: var(--space-md);
    background-color: rgba(214, 48, 49, 0.1);
    border-radius: var(--radius-md);
  }

  .errors h4 {
    margin-bottom: var(--space-sm);
    color: var(--danger);
  }

  .errors ul {
    padding-left: var(--space-lg);
    font-size: 0.875rem;
  }

  .errors li {
    margin-bottom: var(--space-xs);
  }
</style>
