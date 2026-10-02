// Gráficas de Ferrepega (Chart.js). Siguen la guía de visualización del proyecto:
//  - una serie = un solo color; líneas de 2 px; barras delgadas con punta redondeada
//  - rejilla fina y discreta; valor escrito en la punta de cada barra
//  - el texto usa colores de texto, nunca el color de la serie
//  - cada gráfica tiene su tabla equivalente (botón "Ver como tabla")
(function () {
  "use strict";

  var MESES = ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"];
  var MESES_LARGOS = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto",
                      "septiembre", "octubre", "noviembre", "diciembre"];

  // --- Formatos (iguales a los del servidor) --------------------------------------
  function entero(n) { return Math.round(n).toString().replace(/\B(?=(\d{3})+(?!\d))/g, "."); }
  function cop(n) { return "$ " + entero(n); }
  function copCorto(v) {
    var a = Math.abs(v);
    if (a >= 1e6) return "$ " + (v / 1e6).toFixed(1).replace(".", ",").replace(/,0$/, "") + " M";
    if (a >= 1e3) return "$ " + entero(v / 1e3) + " mil";
    return "$ " + entero(v);
  }
  function porcentaje(p) { return p.toFixed(1).replace(".", ",") + " %"; }

  // --- Colores: se leen del CSS, así siguen al tema claro/oscuro -----------------------
  function tokens() {
    var cs = getComputedStyle(document.documentElement);
    function t(n) { return cs.getPropertyValue(n).trim(); }
    return { serie: t("--series-1"), onda: t("--series-wash"), rejilla: t("--grid"), base: t("--baseline"),
             apagado: t("--muted"), tinta: t("--ink"), tinta2: t("--ink-2"), superficie: t("--surface") };
  }
  function conAlfa(hex, alfa) {
    var m = /^#([0-9a-f]{6})$/i.exec(hex);
    if (!m) return hex;
    var n = parseInt(m[1], 16);
    return "rgba(" + (n >> 16) + "," + ((n >> 8) & 255) + "," + (n & 255) + "," + alfa + ")";
  }

  function tooltip(tk, extra) {
    var base = {
      backgroundColor: tk.superficie, titleColor: tk.tinta2, bodyColor: tk.tinta, footerColor: tk.tinta2,
      borderColor: tk.base, borderWidth: 1, padding: 10, cornerRadius: 3, displayColors: false,
      titleFont: { weight: "500", size: 12 }, bodyFont: { weight: "600", size: 14 }, footerFont: { weight: "400", size: 12 },
      caretSize: 0, titleMarginBottom: 4
    };
    for (var k in extra) base[k] = extra[k];
    return base;
  }

  function aplicarDefectos() {
    Chart.defaults.font.family = '"Barlow", system-ui, -apple-system, "Segoe UI", sans-serif';
    Chart.defaults.font.size = 13;
    Chart.defaults.animation.duration = window.matchMedia("(prefers-reduced-motion: reduce)").matches ? 0 : 250;
  }

  // --- Línea de tiempo: ventas por mes ----------------------------------------------------
  var cruz = {
    id: "cruz",
    afterDatasetsDraw: function (chart, _args, op) {
      var t = chart.tooltip;
      if (!t || !t.getActiveElements().length) return;
      var x = t.getActiveElements()[0].element.x, a = chart.chartArea, c = chart.ctx;
      c.save(); c.beginPath(); c.moveTo(x, a.top); c.lineTo(x, a.bottom);
      c.lineWidth = 1; c.strokeStyle = op.color; c.stroke(); c.restore();
    }
  };
  // Etiqueta solo el último punto y el máximo: nunca un número en cada punto
  var etiquetasLinea = {
    id: "etiquetasLinea",
    afterDatasetsDraw: function (chart, _args, op) {
      var meta = chart.getDatasetMeta(0), datos = chart.data.datasets[0].data, n = datos.length;
      if (n < 2) return;
      var idxMax = 0, i;
      for (i = 1; i < n; i++) if (datos[i] > datos[idxMax]) idxMax = i;
      var marcas = [{ i: n - 1, alinear: "right" }];
      if (n - 1 - idxMax >= 3) marcas.push({ i: idxMax, alinear: "center" });
      var c = chart.ctx;
      c.save(); c.font = '600 12px "Barlow", sans-serif'; c.fillStyle = op.color; c.textBaseline = "bottom";
      marcas.forEach(function (m) {
        var p = meta.data[m.i]; c.textAlign = m.alinear;
        c.fillText(copCorto(datos[m.i]), p.x, p.y - 8);
      });
      c.restore();
    }
  };

  function lineaMensual(canvas, serie) {
    var tk = tokens();
    var etiquetas = serie.map(function (m) { return MESES[m.mes - 1] + " " + m.anio; });
    return new Chart(canvas, {
      type: "line",
      plugins: [cruz, etiquetasLinea],
      data: {
        labels: etiquetas,
        datasets: [{
          data: serie.map(function (m) { return m.total_ventas; }),
          borderColor: tk.serie, backgroundColor: tk.onda, fill: "origin",
          borderWidth: 2, borderJoinStyle: "round", tension: 0,
          pointRadius: serie.length < 3 ? 4 : 0, pointBackgroundColor: tk.serie,
          pointHoverRadius: 5, pointHoverBackgroundColor: tk.serie,
          pointHoverBorderColor: tk.superficie, pointHoverBorderWidth: 2, pointHitRadius: 24
        }]
      },
      options: {
        responsive: true, maintainAspectRatio: false,
        interaction: { mode: "index", intersect: false },
        layout: { padding: { top: 22, right: 8 } },
        scales: {
          x: { grid: { display: false }, border: { color: tk.base }, ticks: { color: tk.apagado, maxTicksLimit: 8, maxRotation: 0 } },
          y: { beginAtZero: true, border: { display: false }, grid: { color: tk.rejilla, lineWidth: 1 },
               ticks: { color: tk.apagado, maxTicksLimit: 5, callback: function (v) { return copCorto(v); } } }
        },
        plugins: {
          legend: { display: false },
          cruz: { color: tk.base }, etiquetasLinea: { color: tk.tinta2 },
          tooltip: tooltip(tk, {
            callbacks: {
              title: function (items) { var m = serie[items[0].dataIndex]; return MESES_LARGOS[m.mes - 1] + " " + m.anio; },
              label: function (item) { return cop(item.parsed.y); },
              footer: function (items) { var n = serie[items[0].dataIndex].num_pedidos; return n === undefined ? "" : entero(n) + (n === 1 ? " venta" : " ventas"); }
            }
          })
        }
      }
    });
  }

  // --- Barras horizontales (ranking) -------------------------------------------------------
  // filas: [{ etiqueta, valor, texto (valor en la punta), detalle: [líneas del tooltip] }]
  var valorEnPunta = {
    id: "valorEnPunta",
    afterDatasetsDraw: function (chart, _args, op) {
      var meta = chart.getDatasetMeta(0), filas = op.filas, c = chart.ctx;
      c.save(); c.font = '600 13px "Barlow", sans-serif'; c.fillStyle = op.color; c.textBaseline = "middle"; c.textAlign = "left";
      meta.data.forEach(function (barra, i) { c.fillText(filas[i].texto, barra.x + 8, barra.y); });
      c.restore();
    }
  };

  function barras(canvas, filas, margenDerecho) {
    var tk = tokens();
    var contenedor = canvas.parentElement;
    contenedor.style.height = (filas.length * 34 + 12) + "px";   // alto = filas, sin recortes
    return new Chart(canvas, {
      type: "bar",
      plugins: [valorEnPunta],
      data: {
        labels: filas.map(function (f) { return f.etiqueta; }),
        datasets: [{
          data: filas.map(function (f) { return f.valor; }),
          backgroundColor: tk.serie, hoverBackgroundColor: conAlfa(tk.serie, 0.78),
          borderRadius: { topRight: 4, bottomRight: 4, topLeft: 0, bottomLeft: 0 }, borderSkipped: false,
          barThickness: 18
        }]
      },
      options: {
        indexAxis: "y", responsive: true, maintainAspectRatio: false,
        layout: { padding: { right: margenDerecho || 96 } },
        scales: {
          x: { display: false, beginAtZero: true },
          y: { grid: { display: false }, border: { color: tk.base },
               afterFit: function (escala) {
                 // El eje se ensancha lo justo para las etiquetas, con tope del 45 % del gráfico.
                 var tope = escala.chart.width * 0.45, mayor = 0, c = escala.chart.ctx;
                 c.save(); c.font = '13px "Barlow", sans-serif';
                 filas.forEach(function (f) { mayor = Math.max(mayor, c.measureText(f.etiqueta).width); });
                 c.restore();
                 escala.width = Math.min(mayor, tope) + 14;
               },
               ticks: { color: tk.tinta2, padding: 6, callback: function (v) {
                 var e = this.getLabelForValue(v), c = this.chart.ctx, max = this.chart.width * 0.45;
                 c.save(); c.font = '13px "Barlow", sans-serif';
                 var recortado = false;
                 while (e.length > 3 && c.measureText(e + (recortado ? "…" : "")).width > max) { e = e.slice(0, -1); recortado = true; }
                 c.restore();
                 return recortado ? e.replace(/\s+$/, "") + "…" : e; } } }
        },
        plugins: {
          legend: { display: false },
          valorEnPunta: { filas: filas, color: tk.tinta },
          tooltip: tooltip(tk, {
            callbacks: {
              title: function (items) { return filas[items[0].dataIndex].etiqueta; },
              label: function (item) { return filas[item.dataIndex].detalle; }
            }
          })
        }
      }
    });
  }

  // --- Utilidades para las páginas ------------------------------------------------------------
  // Ejecuta 'dibujar' ahora y cada vez que cambia el tema (botón o preferencia del sistema).
  function conTema(dibujar) {
    var graficas = [];
    function pintar() {
      graficas.forEach(function (g) { g.destroy(); });
      graficas = dibujar() || [];
    }
    pintar();
    document.addEventListener("ferrepega:tema", pintar);
    var mq = window.matchMedia("(prefers-color-scheme: dark)");
    if (mq.addEventListener) mq.addEventListener("change", pintar);
  }

  aplicarDefectos();
  window.Graficas = { lineaMensual: lineaMensual, barras: barras, conTema: conTema,
                      cop: cop, copCorto: copCorto, entero: entero, porcentaje: porcentaje };
})();
