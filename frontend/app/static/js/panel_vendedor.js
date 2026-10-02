// Panel del vendedor: su serie mensual de ventas.
(function () {
  "use strict";
  var datos = JSON.parse(document.getElementById("datos-vendedor").textContent);
  var G = window.Graficas;
  G.conTema(function () {
    return [G.lineaMensual(document.getElementById("g-mensual"), datos.serie.map(function (p) {
      var f = p.fecha.split("-");
      return { anio: +f[0], mes: +f[1], total_ventas: p.total_ventas, num_pedidos: p.num_ventas };
    }))];
  });
})();
