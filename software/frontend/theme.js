// Preferência local; funciona mesmo com armazenamento bloqueado.
(function () {
  const key = 'estacao-viva-tema';
  const media = window.matchMedia('(prefers-color-scheme: dark)');
  let preference = 'system';
  try { const saved = localStorage.getItem(key); if (['light','dark','system'].includes(saved)) preference = saved; } catch (_) {}
  function apply() {
    document.documentElement.dataset.theme = preference === 'system' ? (media.matches ? 'dark' : 'light') : preference;
  }
  apply();
  media.addEventListener('change', () => { if (preference === 'system') apply(); });
  document.addEventListener('DOMContentLoaded', () => {
    const select = document.getElementById('theme-select');
    select.value = preference;
    select.addEventListener('change', () => {
      preference = select.value;
      try { localStorage.setItem(key, preference); } catch (_) {}
      apply();
    });
  });
  window.addEventListener('storage', event => {
    if (event.key !== key && event.key !== null) return;
    preference = ['light','dark','system'].includes(event.newValue) ? event.newValue : 'system';
    apply();
    const select = document.getElementById('theme-select');
    if (select) select.value = preference;
  });
})();
