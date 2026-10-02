"""
Formatos de presentación (moneda, fechas, números) al estilo colombiano.
"""
from datetime import date, datetime
from typing import Optional

MESES = ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"]
MESES_LARGOS = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto",
                "septiembre", "octubre", "noviembre", "diciembre"]


def entero(valor) -> str:
    """1234567 -> 1.234.567"""
    return f"{int(round(float(valor or 0))):,}".replace(",", ".")


def cop(valor) -> str:
    """Pesos colombianos sin decimales: $ 1.234.567 (con centavos solo si los hay)."""
    valor = float(valor or 0)
    if abs(valor - round(valor)) < 0.005:
        return "$ " + entero(valor)
    return "$ " + f"{valor:,.2f}".replace(",", "§").replace(".", ",").replace("§", ".")


def cop_corto(valor) -> str:
    """Para ejes de gráficas: $ 1,2 M / $ 350 mil."""
    v = float(valor or 0)
    if abs(v) >= 1_000_000:
        return "$ " + f"{v / 1_000_000:.1f}".replace(".", ",").rstrip("0").rstrip(",") + " M"
    if abs(v) >= 1_000:
        return "$ " + entero(v / 1_000) + " mil"
    return "$ " + entero(v)


def _a_fecha(valor) -> Optional[datetime]:
    if not valor:
        return None
    if isinstance(valor, (datetime, date)):
        return valor if isinstance(valor, datetime) else datetime.combine(valor, datetime.min.time())
    return datetime.fromisoformat(str(valor)[:19])


def fecha(valor) -> str:
    """2018-10-16T19:20:00 -> 16 oct 2018"""
    d = _a_fecha(valor)
    return f"{d.day} {MESES[d.month - 1]} {d.year}" if d else "—"


def fecha_hora(valor) -> str:
    """-> 16 oct 2018, 7:20 p. m."""
    d = _a_fecha(valor)
    if not d:
        return "—"
    hora12 = d.hour % 12 or 12
    return f"{d.day} {MESES[d.month - 1]} {d.year}, {hora12}:{d.minute:02d} {'a. m.' if d.hour < 12 else 'p. m.'}"


def mes_anio(anio: int, mes: int) -> str:
    return f"{MESES[mes - 1]} {anio}"


def fecha_iso(valor) -> str:
    d = _a_fecha(valor)
    return d.strftime("%Y-%m-%d") if d else ""
