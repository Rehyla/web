from django import template

register = template.Library()

@register.filter
def multiply(value, arg):
    """Multiplica el valor por el argumento"""
    try:
        return float(value) * float(arg)
    except (ValueError, TypeError):
        return 0

@register.filter
def sum_detalle_total(detalle_list):
    """Suma el total de precio*cantidad para una lista de objetos DetallePedido"""
    total = 0
    for detalle in detalle_list:
        try:
            total += detalle.precio * detalle.cantidad
        except (TypeError, ValueError):
            # En caso de que precio o cantidad no sean números
            continue
    # Devuelve el total con formato de dos decimales (opcional)
    return "{:,.0f}".format(total).replace(",", ".")