// Settings: one JSON record holding every value the app uses, readable in a
// problem report. localStorage on device; export() is what the report embeds.
export function settings(key, defaults) {
  let data = { ...defaults };
  try { data = { ...defaults, ...JSON.parse(localStorage.getItem(key) || '{}') }; } catch (e) {}
  return {
    get: (k) => data[k],
    set(k, v) { data[k] = v; try { localStorage.setItem(key, JSON.stringify(data)); } catch (e) {} },
    reset() { data = { ...defaults }; try { localStorage.removeItem(key); } catch (e) {} },
    export: () => ({ ...data }),
    defaults: () => ({ ...defaults }),
  };
}
