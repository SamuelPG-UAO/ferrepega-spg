// Se ejecuta en <head>, antes de pintar la página: aplica el tema guardado y evita el parpadeo.
(function () {
  try {
    var t = localStorage.getItem("ferrepega-tema");
    if (t === "dark" || t === "light") document.documentElement.setAttribute("data-theme", t);
  } catch (e) { /* sin almacenamiento: se usa el tema del sistema */ }
})();
