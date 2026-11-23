/* Ayuda de navegación, no una medida de seguridad: el navegador conserva el control.
   Seguridad real: middleware no-store + validación de sesión y rol en servidor. */
(() => {
  if (window.history && typeof window.history.pushState === 'function') {
    try { window.history.pushState({cafeNoAtras: true}, '', window.location.href); } catch (_) {}
    window.addEventListener('popstate', () => {
      try { window.history.pushState({cafeNoAtras: true}, '', window.location.href); } catch (_) {}
    });
  }
  window.addEventListener('pageshow', (evento) => {
    if (evento.persisted) window.location.reload();
  });
})();
