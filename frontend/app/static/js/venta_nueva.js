// Pantalla "Nueva venta": busca productos y clientes, arma el carrito y confirma.
// El total que se ve aquí es solo informativo: el precio real lo pone el servidor.
(function () {
  "use strict";

  var carrito = [];          // [{id, nombre, precio, stock, cantidad}]
  var cliente = null;        // {id, nombre} o null (venta de mostrador)
  var csrf = document.querySelector('meta[name="csrf-token"]').content;

  var $ = function (id) { return document.getElementById(id); };
  var cop = function (n) { return "$ " + Math.round(n).toString().replace(/\B(?=(\d{3})+(?!\d))/g, "."); };

  function esperar(fn, ms) {                    // evita una búsqueda por cada tecla
    var t; return function () { var a = arguments, c = this; clearTimeout(t); t = setTimeout(function () { fn.apply(c, a); }, ms); };
  }
  function texto(el, s) { el.textContent = s; return el; }
  function nodo(tag, clase, s) { var e = document.createElement(tag); if (clase) e.className = clase; if (s !== undefined) e.textContent = s; return e; }

  // --- Productos -----------------------------------------------------------------------
  var buscarProductos = esperar(function () {
    var q = $("buscar-producto").value.trim();
    fetch("/ventas/buscar-productos?q=" + encodeURIComponent(q), { credentials: "same-origin" })
      .then(function (r) { if (!r.ok) throw new Error(); return r.json(); })
      .then(function (lista) {
        var ul = $("resultados-productos"); ul.textContent = "";
        if (!lista.length) { ul.appendChild(nodo("li", "muted", q ? "No hay productos disponibles con ese nombre." : "No hay productos disponibles.")); return; }
        lista.forEach(function (p) {
          var li = nodo("li"), info = nodo("div");
          info.appendChild(nodo("span", "nombre", p.nombre));
          info.appendChild(nodo("small", "", p.categoria + " · " + cop(p.precio) + " · " + p.stock + " en stock"));
          var b = nodo("button", "btn btn-sec btn-mini", "Agregar"); b.type = "button";
          b.addEventListener("click", function () { agregar(p); });
          li.appendChild(info); li.appendChild(b); ul.appendChild(li);
        });
      })
      .catch(function () { texto($("resultados-productos"), "No se pudo buscar. Intenta de nuevo."); });
  }, 250);

  function agregar(p) {
    var existente = carrito.filter(function (i) { return i.id === p.id; })[0];
    if (existente) existente.cantidad = Math.min(existente.cantidad + 1, existente.stock);
    else carrito.push({ id: p.id, nombre: p.nombre, precio: p.precio, stock: p.stock, cantidad: 1 });
    pintarCarrito();
  }

  function pintarCarrito() {
    var tabla = $("tabla-carrito"), cuerpo = tabla.querySelector("tbody"), total = 0;
    cuerpo.textContent = "";
    carrito.forEach(function (i, idx) {
      var tr = nodo("tr"), td1 = nodo("td"), td2 = nodo("td", "num"), td3 = nodo("td", "num"), td4 = nodo("td");
      td1.appendChild(nodo("span", "producto-nombre", i.nombre));
      td1.appendChild(nodo("span", "sub", cop(i.precio) + " c/u · máx. " + i.stock));
      var inp = nodo("input"); inp.type = "number"; inp.min = 1; inp.max = i.stock; inp.value = i.cantidad;
      inp.setAttribute("aria-label", "Cantidad de " + i.nombre);
      inp.addEventListener("change", function () {
        var v = parseInt(inp.value, 10);
        i.cantidad = isNaN(v) || v < 1 ? 1 : Math.min(v, i.stock);
        pintarCarrito();
      });
      td2.appendChild(inp);
      td3.textContent = cop(i.precio * i.cantidad);
      var q = nodo("button", "btn btn-sec btn-mini", "Quitar"); q.type = "button";
      q.addEventListener("click", function () { carrito.splice(idx, 1); pintarCarrito(); });
      td4.appendChild(q);
      [td1, td2, td3, td4].forEach(function (td) { tr.appendChild(td); });
      cuerpo.appendChild(tr);
      total += i.precio * i.cantidad;
    });
    tabla.hidden = carrito.length === 0;
    $("carrito-vacio").hidden = carrito.length > 0;
    $("total-venta").textContent = cop(total);
    $("confirmar-venta").disabled = carrito.length === 0;
  }

  // --- Cliente --------------------------------------------------------------------------------
  var buscarClientes = esperar(function () {
    var q = $("buscar-cliente").value.trim(), ul = $("resultados-clientes");
    if (q.length < 2) { ul.textContent = ""; return; }
    fetch("/ventas/buscar-clientes?q=" + encodeURIComponent(q), { credentials: "same-origin" })
      .then(function (r) { if (!r.ok) throw new Error(); return r.json(); })
      .then(function (lista) {
        ul.textContent = "";
        if (!lista.length) { ul.appendChild(nodo("li", "muted", "No hay clientes con ese nombre.")); return; }
        lista.forEach(function (c) {
          var li = nodo("li"), info = nodo("div");
          info.appendChild(nodo("span", "nombre", c.nombre));
          info.appendChild(nodo("small", "", [c.correo, c.ciudad].filter(Boolean).join(" · ") || "Sin más datos"));
          var b = nodo("button", "btn btn-sec btn-mini", "Elegir"); b.type = "button";
          b.addEventListener("click", function () { elegirCliente(c); });
          li.appendChild(info); li.appendChild(b); ul.appendChild(li);
        });
      })
      .catch(function () { texto(ul, "No se pudo buscar. Intenta de nuevo."); });
  }, 250);

  function elegirCliente(c) {
    cliente = c;
    $("resultados-clientes").textContent = ""; $("buscar-cliente").value = "";
    var p = $("cliente-elegido"); p.textContent = "";
    p.appendChild(nodo("strong", "", c.nombre));
    p.appendChild(document.createTextNode(" "));
    var q = nodo("button", "enlace-boton", "Quitar cliente"); q.type = "button";
    q.addEventListener("click", function () {
      cliente = null; p.textContent = "Venta de mostrador (sin cliente).";
    });
    p.appendChild(q);
  }

  // --- Confirmar --------------------------------------------------------------------------------
  $("confirmar-venta").addEventListener("click", function () {
    var boton = this, error = $("error-venta");
    error.hidden = true; boton.disabled = true; boton.textContent = "Registrando…";
    fetch("/ventas/nueva", {
      method: "POST", credentials: "same-origin",
      headers: { "Content-Type": "application/json", "X-CSRF-Token": csrf },
      body: JSON.stringify({ cliente_id: cliente ? cliente.id : null,
                             items: carrito.map(function (i) { return { producto_id: i.id, cantidad: i.cantidad }; }) })
    }).then(function (r) { return r.json().then(function (d) { return { ok: r.ok, datos: d }; }); })
      .then(function (res) {
        if (res.ok && res.datos.ok) { window.location.href = res.datos.destino; return; }
        error.textContent = res.datos.mensaje || "No se pudo registrar la venta."; error.hidden = false;
        boton.disabled = false; boton.textContent = "Confirmar venta";
        buscarProductos();   // refresca los stocks que se muestran
      })
      .catch(function () {
        error.textContent = "No se pudo conectar con el servidor. Revisa tu conexión e inténtalo de nuevo."; error.hidden = false;
        boton.disabled = false; boton.textContent = "Confirmar venta";
      });
  });

  $("buscar-producto").addEventListener("input", buscarProductos);
  $("buscar-cliente").addEventListener("input", buscarClientes);
  buscarProductos();
  pintarCarrito();
})();
