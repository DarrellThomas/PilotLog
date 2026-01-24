/**
 * Settings store with localStorage persistence.
 */

// Map tile themes available
export const mapThemes = {
  dark: {
    name: 'Dark',
    url: 'https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png',
    attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OSM</a> &copy; <a href="https://carto.com/attributions">CARTO</a>',
  },
  light: {
    name: 'Light',
    url: 'https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png',
    attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OSM</a> &copy; <a href="https://carto.com/attributions">CARTO</a>',
  },
  voyager: {
    name: 'Voyager',
    url: 'https://{s}.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}{r}.png',
    attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OSM</a> &copy; <a href="https://carto.com/attributions">CARTO</a>',
  },
  satellite: {
    name: 'Satellite',
    url: 'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
    attribution: '&copy; Esri &mdash; Source: Esri, i-cubed, USDA, USGS, AEX, GeoEye, Getmapping, Aerogrid, IGN, IGP, UPR-EGP, and the GIS User Community',
  },
  terrain: {
    name: 'Terrain',
    url: 'https://stamen-tiles-{s}.a.ssl.fastly.net/terrain/{z}/{x}/{y}{r}.png',
    attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OSM</a> &copy; <a href="https://stamen.com">Stamen Design</a>',
  },
  osm: {
    name: 'OpenStreetMap',
    url: 'https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png',
    attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
  },
};

// Route color options
export const routeColors = {
  canyonBlue: { name: 'Canyon Blue (Southwest)', color: '#304CB2', light: '#5d7fca' },
  yellow: { name: 'Yellow', color: '#ffeb3b', light: '#ffd700' },
  magenta: { name: 'Magenta', color: '#e84393', light: '#f78fb3' },
  cyan: { name: 'Cyan', color: '#00bcd4', light: '#4dd0e1' },
  orange: { name: 'Orange', color: '#ff9800', light: '#ffb74d' },
  green: { name: 'Green', color: '#4caf50', light: '#81c784' },
  white: { name: 'White', color: '#ffffff', light: '#e0e0e0' },
};

const STORAGE_KEY = 'pilotlog_settings';

const defaultSettings = {
  mapTheme: 'light',
  routeColor: 'canyonBlue',
};

// Load settings from localStorage
function loadSettings() {
  try {
    const stored = localStorage.getItem(STORAGE_KEY);
    if (stored) {
      return { ...defaultSettings, ...JSON.parse(stored) };
    }
  } catch (e) {
    console.warn('Failed to load settings:', e);
  }
  return { ...defaultSettings };
}

// Save settings to localStorage
function saveSettings(settings) {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(settings));
  } catch (e) {
    console.warn('Failed to save settings:', e);
  }
}

// Simple reactive store
let settings = loadSettings();
let subscribers = [];

export function getSettings() {
  return settings;
}

export function updateSettings(newSettings) {
  settings = { ...settings, ...newSettings };
  saveSettings(settings);
  subscribers.forEach(fn => fn(settings));
}

export function subscribeSettings(fn) {
  subscribers.push(fn);
  fn(settings); // Call immediately with current value
  return () => {
    subscribers = subscribers.filter(s => s !== fn);
  };
}
