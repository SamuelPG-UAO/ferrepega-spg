"""
Cálculo de los resúmenes a partir de las ventas.

Es una función "pura" (no toca bases de datos ni red): recibe ventas y devuelve
filas. Por eso es fácil de probar sola.
"""
from collections import defaultdict
from datetime import datetime
from decimal import Decimal
from typing import Iterable


def dinero(valor) -> Decimal:
    """float -> Decimal con centavos (pasando por texto para no arrastrar error binario)."""
    return Decimal(str(valor)).quantize(Decimal("0.01"))


def calcular(ventas: Iterable[dict]) -> dict:
    mensual = defaultdict(lambda: [Decimal("0"), 0])      # (anio, mes) -> [total, pedidos]
    productos = {}                                        # id -> [nombre, unidades, ingresos]
    categorias = defaultdict(lambda: [Decimal("0"), 0])   # nombre -> [total, unidades]
    por_vendedor = defaultdict(lambda: [Decimal("0"), 0])  # (vendedor, dia) -> [total, ventas]
    n = 0

    for v in ventas:
        n += 1
        fecha = datetime.fromisoformat(v["fecha"])
        total = dinero(v["total"])

        m = mensual[(fecha.year, fecha.month)]
        m[0] += total
        m[1] += 1

        d = por_vendedor[(v["vendedor_id"], fecha.date())]
        d[0] += total
        d[1] += 1

        for it in v["items"]:
            sub = dinero(it["subtotal"])
            p = productos.setdefault(it["producto_id"], [it["nombre_producto"], 0, Decimal("0")])
            p[0] = it["nombre_producto"]  # queda el nombre más reciente
            p[1] += it["cantidad"]
            p[2] += sub
            c = categorias[it["categoria"]]
            c[0] += sub
            c[1] += it["cantidad"]

    return {
        "ventas_procesadas": n,
        "mensuales": [dict(anio=a, mes=m, total_ventas=t, num_pedidos=k)
                      for (a, m), (t, k) in sorted(mensual.items())],
        "productos": [dict(producto_id=i, nombre=nom, unidades=u, ingresos=ing)
                      for i, (nom, u, ing) in sorted(productos.items())],
        "categorias": [dict(categoria=c, total_ventas=t, unidades=u)
                       for c, (t, u) in sorted(categorias.items())],
        "vendedores": [dict(vendedor_id=vid, fecha=dia, total_ventas=t, num_ventas=k)
                       for (vid, dia), (t, k) in sorted(por_vendedor.items())],
    }
