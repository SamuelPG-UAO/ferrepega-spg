// Comportamientos comunes de la interfaz. No hay JavaScript "en línea": todo vive en archivos .js.
(function () {
  "use strict";

  // --- Tema claro / oscuro ---------------------------------------------------
  var botonTema = document.getElementById("cambiar-tema");
  if (botonTema) {
    botonTema.addEventListener("click", function () {
      var actual = document.documentElement.getAttribute("data-theme") ||
        (window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light");
      var nuevo = actual === "dark" ? "light" : "dark";
      document.documentElement.setAttribute("data-theme", nuevo);
      try { localStorage.setItem("ferrepega-tema", nuevo); } catch (e) { /* no pasa nada */ }
      document.dispatchEvent(new CustomEvent("ferrepega:tema"));  // las gráficas se redibujan
    });
  }

  // --- Menú en pantallas angostas ---------------------------------------------
  var abrir = document.getElementById("abrir-menu"), lateral = document.getElementById("lateral");
  if (abrir && lateral) {
    abrir.addEventListener("click", function () {
      var abierto = lateral.classList.toggle("abierto");
      abrir.setAttribute("aria-expanded", abierto ? "true" : "false");
    });
    document.getElementById("contenido").addEventListener("click", function () {
      lateral.classList.remove("abierto"); abrir.setAttribute("aria-expanded", "false");
    });
  }

  // --- Diálogos con formulario -------------------------------------------------
  // <button data-dialogo="id" data-accion="/ruta" data-rellenar='{"campo": "valor"}'>
  document.addEventListener("click", function (ev) {
    var b = ev.target.closest("[data-dialogo]");
    if (b) {
      var d = document.getElementById(b.getAttribute("data-dialogo"));
      if (!d) return;
      var f = d.querySelector("form");
      if (b.dataset.accion && f) f.setAttribute("action", b.dataset.accion);
      var datos = b.dataset.rellenar ? JSON.parse(b.dataset.rellenar) : {};
      if (f) {
        Array.prototype.forEach.call(f.elements, function (el) {
          if (!el.name || el.name === "csrf_token") return;
          var v = Object.prototype.hasOwnProperty.call(datos, el.name) ? datos[el.name] : undefined;
          if (el.type === "checkbox") el.checked = v === undefined ? el.defaultChecked : !!v;
          else if (v !== undefined) el.value = v;
          else if (b.dataset.limpiar !== undefined) el.value = el.defaultValue;
        });
        var t = d.querySelector("[data-titulo]");
        if (t && b.dataset.titulo) t.textContent = b.dataset.titulo;
      }
      d.showModal();
      var primero = d.querySelector("input:not([type=hidden]), select, textarea");
      if (primero) primero.focus();
      return;
    }
    var c = ev.target.closest("[data-cerrar]");
    if (c) { var dd = c.closest("dialog"); if (dd) dd.close(); }
  });

  // --- Confirmación antes de acciones delicadas --------------------------------
  document.addEventListener("submit", function (ev) {
    var msg = ev.target.getAttribute("data-confirmar");
    if (msg && !window.confirm(msg)) ev.preventDefault();
  });

  // --- "Ver como tabla": cada gráfica tiene una tabla equivalente ---------------
  document.addEventListener("click", function (ev) {
    var b = ev.target.closest("[data-alternar]");
    if (!b) return;
    var panel = b.closest("[data-panel-grafica]");
    var g = panel.querySelector(".vista-grafica"), t = panel.querySelector(".vista-tabla");
    var verTabla = t.hidden;
    t.hidden = !verTabla; g.hidden = verTabla;
    b.setAttribute("aria-pressed", verTabla ? "true" : "false");
    b.textContent = verTabla ? "Ver como gráfica" : "Ver como tabla";
  });

  // --- Cuentas de demostración del login ---------------------------------------
  document.addEventListener("click", function (ev) {
    var b = ev.target.closest("[data-demo-correo]");
    if (!b) return;
    document.getElementById("correo").value = b.dataset.demoCorreo;
    document.getElementById("contrasena").value = b.dataset.demoClave;
    document.getElementById("contrasena").focus();
  });
})();
