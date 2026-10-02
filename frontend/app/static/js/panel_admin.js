// Panel del administrador: arma las 4 gráficas con los datos que Flask dejó en la página.
(function () {
  "use strict";
  var datos = JSON.parse(document.getElementById("datos-panel").textContent);
  var G = window.Graficas;

  G.conTema(function () {
    var graficas = [];
    graficas.push(G.lineaMensual(document.getElementById("g-mensual"), datos.mensuales));

    graficas.push(G.barras(document.getElementById("g-top"), datos.top.map(function (p) {
      var porUnidades = datos.metrica === "unidades";
      return {
        etiqueta: p.nombre, valor: porUnidades ? p.unidades : p.ingresos,
        texto: porUnidades ? G.entero(p.unidades) + " u." : G.copCorto(p.ingresos),
        detalle: [G.cop(p.ingresos), G.entero(p.unidades) + " unidades"]
      };
    })));

    graficas.push(G.barras(document.getElementById("g-categorias"), datos.categorias.map(function (c) {
      return { etiqueta: c.categoria, valor: c.total_ventas,
               texto: G.copCorto(c.total_ventas) + " · " + G.porcentaje(c.porcentaje),
               detalle: [G.cop(c.total_ventas), G.entero(c.unidades) + " unidades"] };
    }), 150));

    graficas.push(G.barras(document.getElementById("g-vendedores"), datos.vendedores.map(function (v) {
      return { etiqueta: v.nombre, valor: v.total_ventas, texto: G.copCorto(v.total_ventas),
               detalle: [G.cop(v.total_ventas), G.entero(v.num_ventas) + " ventas"] };
    })));
    return graficas;
  });
})();
