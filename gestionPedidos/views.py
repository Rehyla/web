
# IMPORTS NUEVOS EXCLUSIVOS DE COCINA
import json
import re
import hashlib
from base64 import b64encode
from io import BytesIO
from math import ceil
from pathlib import Path
from django.conf import settings
from django.core.files.storage import default_storage
from django.contrib.auth.hashers import make_password, check_password
from django.utils.crypto import constant_time_compare
from django.contrib import messages
from django.http import JsonResponse, HttpResponseForbidden
from django.views.decorators.http import require_GET, require_POST, require_http_methods
from django.views.decorators.cache import never_cache
from django.db import transaction, IntegrityError
from zoneinfo import ZoneInfo
from .forms import EncuestaSatisfaccionForm
from .models import EncuestaSatisfaccion, EstadoPedidoCocina

import openpyxl
import qrcode
from openpyxl.styles import Font
from django.http import HttpResponse

from django.shortcuts import render, redirect, get_object_or_404
from .models import Usuario, Producto, Pedido, DetallePedido
from django.urls import reverse
from django.utils import timezone
from django.db.models import Avg, Case, Count, F, IntegerField, Q, Sum, Value, When
from datetime import datetime # <--- Deja solo datetime
from django.db.models.functions import TruncMonth, TruncDay
import time
from django.http import HttpResponseForbidden



# === ===  === ===  === === 
# MENU 2
# === ===  === ===  === === 
REFERENCIA_ATENCION_SEGUNDOS = 120
LIMITE_ATENCION_SEGUNDOS = 240


def _iniciar_atencion(request):
    if request.session.get('inicio_atencion') is None:
        request.session['inicio_atencion'] = time.time()


def _segundos_atencion(request):
    inicio = request.session.get('inicio_atencion')
    return max(0, ceil(time.time() - inicio)) if inicio is not None else None


def _cerrar_carrito(request):
    request.session['carrito'] = {}
    request.session.pop('inicio_atencion', None)


@require_POST
def controlar_atencion(request):
    if request.session.get('rol') not in ('Admin', 'Vendedor'):
        return HttpResponseForbidden('Sin permisos para registrar la atención.')
    if not request.session.get('carrito'):
        accion = request.POST.get('accion')
        if accion == 'iniciar':
            _iniciar_atencion(request)
        elif accion == 'cancelar':
            _cerrar_carrito(request)
    opcion = {'3': 3, '4': 4, '5': 5}.get(request.POST.get('opcion'), 3)
    return redirect('menu2', opcion=opcion)


def menu2(request, opcion=1):
    nombre = request.session.get('usuarioLogeado')
    carrito = request.session.get('carrito',{})
    total = sum(item["precio"] * item["cantidad"] for item in carrito.values()) 
    
    # 1. Definir el mapeo de categorías
    categoria_map = {
        1: {'db_name': 'Almuerzo', 'title': '🍽️ Almuerzo'},
        2: {'db_name': 'Sopa', 'title': '🥣 Sopas'},
        3: {'db_name': 'Bebida', 'title': '🥤 Bebidas'},
        4: {'db_name': 'Postre', 'title': '🍮 Postres'},
        5: {'db_name': 'Salado', 'title': '🥟 Salados'},
    }
    
    # 2. Obtener la información de la categoría seleccionada (default a Almuerzo si es inválida)
    categoria_info = categoria_map.get(opcion, categoria_map[1])
    categoria_db_name = categoria_info['db_name']
    categoria_titulo = categoria_info['title']

    # 3. Filtrar los productos por la categoría de la DB
    pro = Producto.objects.filter(categoria=categoria_db_name)

    datos = {
        'nombre':nombre,
        'pro': pro, # 'pro' ahora solo tiene los productos filtrados
        'carrito': carrito,
        'total': total,
        'opcion': opcion,
        'categoria_actual_nombre': categoria_titulo,
        'segundos_atencion': _segundos_atencion(request),
        'limite_atencion': LIMITE_ATENCION_SEGUNDOS,
        'limite_atencion_min': LIMITE_ATENCION_SEGUNDOS // 60,
    }
    return render(request, "Menu2.html", datos)

# NOTA: Asegúrate de que tu modelo Producto.categoria usa exactamente los nombres 'Almuerzo', 'Sopa', etc.

def finalizar3(request):

    usuario_nombre = request.session.get("usuarioLogeado")
    usu_db = Usuario.objects.filter(nombres=usuario_nombre).first()
    if not usu_db:
        # Asegúrate de que esta URL de redirección sea correcta (puse 'menu/1' como ejemplo de la conversación anterior, pero el snippet usa 'menu')
        return redirect("menu2") 
        
    carrito = request.session.get("carrito", {})
    
    if not carrito:
        return redirect("/menu3/") 

    # 🔑 PASO 1: CAPTURAR EL MÉTODO DE PAGO DEL FORMULARIO
    # Busca el valor enviado desde el formulario (name="tipoPago").
    # Si por alguna razón no se envía nada, usa 'Efectivo' como valor por defecto.
    tipo_pago_seleccionado = request.POST.get("tipoPago", "Efectivo") 

    total = sum(item["precio"] * item["cantidad"] for item in carrito.values())

    # Crear el pedido
    pedido = Pedido.objects.create(
        usuario=usu_db,
        # La hora es capturada correctamente usando la zona horaria de Django.
        fecha=timezone.now(),
        # 🔑 PASO 2: USAR LA VARIABLE CAPTURADA EN LUGAR DE UN VALOR FIJO
        tipoPago=tipo_pago_seleccionado, 
        total=total,
        estado=1,
        duracion_atencion_segundos=_segundos_atencion(request),
    )
    # Ya no se necesita `pedido.save()` porque .create() lo guarda automáticamente.
    
    # Crear detalles del pedido
    for key, item in carrito.items():
        DetallePedido.objects.create(
            pedido=pedido,
            producto=Producto.objects.get(id=int(key)),
            cantidad=item["cantidad"],
            precio=item["precio"]
        )

    # Vaciar carrito
    _cerrar_carrito(request)

    opcion = 1

    if opcion == 1:
        pro = Producto.objects.filter(categoria='Almuerzo')

    elif opcion == 2:
        pro = Producto.objects.filter(categoria='Sopa')

    elif opcion == 3:
        pro = Producto.objects.filter(categoria='Bebida')

    elif opcion == 4:
        pro = Producto.objects.filter(categoria='Postre')
    elif opcion == 5:
        pro = Producto.objects.filter(categoria='Salado')

    nombre = request.session.get('usuarioLogeado')


    carrito = request.session.get('carrito', {})
    total = sum(item["precio"] * item["cantidad"] for item in carrito.values()) 

    datos = {
        'pro': pro,
        'nombre': nombre,
        'opcion': opcion,
        'carrito': carrito,
        'total': total,

        'proceso':1,
        'procesoNombre':'ingresado'
    }
    

    return render(request, "Menu3.html", datos)

def agregar_carrito_menu3(request, producto_id):
    # **CAMBIO ACEPTAR SOLO POST**
    if request.method != 'POST':
        return redirect("menu3_default")
        
    carrito = request.session.get('carrito', {})
    
    # 1. Obtener el producto base
    try:
        producto = Producto.objects.get(id=producto_id)
    except Producto.DoesNotExist:
        print(f"Producto ID {producto_id} no encontrado.")
        return redirect("menu3_default")

    # 2. Determinar el nombre y la opción de retorno
    if producto.categoria == 'Almuerzo':
        nombre_a_mostrar = "Almuerzo"
        opcion_retorno = 1
    elif producto.categoria == 'Sopa':
        nombre_a_mostrar = "Sopa"
        opcion_retorno = 2
    elif producto.categoria == 'Bebida':
        nombre_a_mostrar = "Bebida"
        opcion_retorno = 3
    elif producto.categoria == 'Postre':
        nombre_a_mostrar = "Postre"
        opcion_retorno = 4
    elif producto.categoria == 'Salado':
        nombre_a_mostrar = 'Salado'
        opcion_retorno = 5
    else:
        nombre_a_mostrar = producto.nombre 
        opcion_retorno = 1

    # 💥 CAMBIO CRÍTICO: Leer la cantidad del formulario POST
    try:
        cantidad = int(request.POST.get('cantidad', 1)) 
        if cantidad <= 0:
            cantidad = 1
    except ValueError:
        cantidad = 1
    
    # 3. Generar un ID ÚNICO
    # Importante: El ID único asegura que cada clic es un ítem nuevo.
    import time
    unique_cart_id = f"{producto_id}_{int(time.time() * 1000)}" 
    
    # 💥 CAMBIO CRÍTICO: NO AGREGAR LÓGICA DE COMPROBACIÓN. 
    # Simplemente añadir el nuevo ítem con la clave única.
    # El 'nombre' del producto en el carrito se establece como la categoría base.
    if not carrito:
        _iniciar_atencion(request)
    carrito[unique_cart_id] = {
        # Usamos la categoría como nombre a mostrar en el carrito de Menu2.html
        "nombre": nombre_a_mostrar, 
        "precio": producto.precio, # Precio UNITARIO
        "cantidad": cantidad,
        "producto_id_real": producto_id 
    }
    
    # 4. Guardar en la sesión y forzar la actualización
    request.session['carrito'] = carrito
    request.session.modified = True 
    
    # 5. Redirigir directamente para forzar la recarga del menú 2
    return redirect('menu3', opcion=opcion_retorno)











def agregar_carrito_menu2(request, producto_id):
    # **CAMBIO ACEPTAR SOLO POST**
    if request.method != 'POST':
        return redirect("menu2_default")
        
    carrito = request.session.get('carrito', {})
    
    # 1. Obtener el producto base
    try:
        producto = Producto.objects.get(id=producto_id)
    except Producto.DoesNotExist:
        print(f"Producto ID {producto_id} no encontrado.")
        return redirect("menu2_default")

    # 2. Determinar el nombre y la opción de retorno
    if producto.categoria == 'Almuerzo':
        nombre_a_mostrar = "Almuerzo"
        opcion_retorno = 1
    elif producto.categoria == 'Sopa':
        nombre_a_mostrar = "Sopa"
        opcion_retorno = 2
    elif producto.categoria == 'Bebida':
        nombre_a_mostrar = "Bebida"
        opcion_retorno = 3
    elif producto.categoria == 'Postre':
        nombre_a_mostrar = "Postre"
        opcion_retorno = 4
    elif producto.categoria == 'Salado':
        nombre_a_mostrar = 'Salado'
        opcion_retorno = 5
    else:
        nombre_a_mostrar = producto.nombre 
        opcion_retorno = 1

    # 💥 CAMBIO CRÍTICO: Leer la cantidad del formulario POST
    try:
        cantidad = int(request.POST.get('cantidad', 1)) 
        if cantidad <= 0:
            cantidad = 1
    except ValueError:
        cantidad = 1
    
    # 3. Generar un ID ÚNICO
    # Importante: El ID único asegura que cada clic es un ítem nuevo.
    import time
    unique_cart_id = f"{producto_id}_{int(time.time() * 1000)}" 
    
    # 💥 CAMBIO CRÍTICO: NO AGREGAR LÓGICA DE COMPROBACIÓN. 
    # Simplemente añadir el nuevo ítem con la clave única.
    # El 'nombre' del producto en el carrito se establece como la categoría base.
    if not carrito:
        _iniciar_atencion(request)
    carrito[unique_cart_id] = {
        # Usamos la categoría como nombre a mostrar en el carrito de Menu2.html
        "nombre": nombre_a_mostrar, 
        "precio": producto.precio, # Precio UNITARIO
        "cantidad": cantidad,
        "producto_id_real": producto_id 
    }
    
    # 4. Guardar en la sesión y forzar la actualización
    request.session['carrito'] = carrito
    request.session.modified = True 
    
    # 5. Redirigir directamente para forzar la recarga del menú 2
    return redirect('menu2', opcion=opcion_retorno)





















@never_cache
def mostrarIndex(request):
    # No presentar login a alguien que ya ingresó (también al usar Atrás).
    if request.session.get('estadoSesion') is True:
        rol = request.session.get('rol')
        if rol == 'Admin':
            return redirect('menuAdmin')
        if rol == 'Cocina':
            return redirect('menuCocina')
        if rol == 'Vendedor':
            if request.session.get('complejidad') == 'Media':
                return redirect('menu2', opcion=3)
            return redirect('menu', opcion=1)
    return render(request, 'Index.html')

def mostrarMenu(request, opcion):

    estadoSesion = request.session.get('estadoSesion')

    if not opcion:
        opcion = 1


    if estadoSesion == True:

        nombre = request.session.get('usuarioLogeado')

        carrito = request.session.get('carrito', {})
        total = sum(item["precio"] * item["cantidad"] for item in carrito.values()) 
        # pro = Producto.objects.all().values()

        if opcion == 1:
            pro = Producto.objects.filter(categoria='Almuerzo')

        elif opcion == 2:
            pro = Producto.objects.filter(categoria='Sopa')

        elif opcion == 3:
            pro = Producto.objects.filter(categoria='Bebida')

        elif opcion == 4:
            pro = Producto.objects.filter(categoria='Postre')
        elif opcion == 5:
            pro = Producto.objects.filter(categoria='Salado')
        

        datos = {
            'pro': pro,
            'nombre': nombre,
            'opcion':opcion,
            'carrito': carrito,
            'total': total
        }
            
        return render(request, 'Menu.html', datos)
    
    else:
        datos = {'error': 0}
        return render(request, 'index.html', datos)
        
    


def mostrarMenuAdmin(request):

    estadoSesion = request.session.get('estadoSesion')
    rol = request.session.get('rol')




    if estadoSesion == True:
        if rol == 'Admin':

            nombre = request.session.get('usuarioLogeado')

            datos = {
                'nombre': nombre
            }


            
            return render(request, 'Admin.html', datos)
        

        else:


            datos = {'error': 1}
            return render(request, 'index.html', datos)
    else:
        datos = {'error': 0}
        return render(request, 'index.html', datos)
    

# ===  ===  ===  ===  ===  ===  ===  === 
# Views dentro del MENU ADMIN 
# ===  ===  ===  ===  ===  ===  ===  === 
    

def mostrarPedido(request):
    estadoSesion = request.session.get('estadoSesion')
    rol = request.session.get('rol')


    if estadoSesion == True:

        if rol == 'Admin':

            nombre = request.session.get('usuarioLogeado')
            pro = Producto.objects.all().values()

            datos = {
                'pro': pro,
                'nombre': nombre
            }
            
            return render(request, 'Pedido.html', datos)
        
        else:

            datos = {'error': 1}
            return render(request, 'index.html', datos)
    else:
        datos = {'error': 0}
        return render(request, 'index.html', datos)

def mostrarHistorial(request):

    estadoSesion = request.session.get('estadoSesion')
    rol = request.session.get('rol')


    if estadoSesion == True:
        if rol == 'Admin':

            nombre_logeado = request.session.get('usuarioLogeado')

            # Obtener los parámetros de filtro de la URL
            usuario_filtro = request.GET.get('usuario_filtro', '').strip()
            fecha_inicio_str = request.GET.get('fecha_inicio')
            fecha_fin_str = request.GET.get('fecha_fin')

            # Obtener todos los DetallePedido para la base
            pedidos_detalle = DetallePedido.objects.all().select_related(
                'pedido__usuario', 
                'producto'
            ).order_by('-pedido__fecha') # Ordenar por fecha descendente

            # Aplicar filtro de usuario (Vendedor) si se proporciona
            if usuario_filtro:
                # Filtrar si el nombre O apellido del usuario (vendedor) contiene el texto
                pedidos_detalle = pedidos_detalle.filter(
                    Q(pedido__usuario__nombres__icontains=usuario_filtro) |
                    Q(pedido__usuario__apellidos__icontains=usuario_filtro)
                )

            # Aplicar filtro de rango de fechas
            if fecha_inicio_str:
                try:
                    # Convertir la fecha de inicio a un objeto datetime (a medianoche)
                    fecha_inicio = datetime.strptime(fecha_inicio_str, '%Y-%m-%d').date()
                    pedidos_detalle = pedidos_detalle.filter(pedido__fecha__date__gte=fecha_inicio)
                except ValueError:
                    pass # Ignorar si el formato de fecha es incorrecto
            
            if fecha_fin_str:
                try:
                    # Convertir la fecha de fin a un objeto datetime (a las 23:59:59)
                    # Esto asegura que se incluyan todos los pedidos de ese día
                    fecha_fin = datetime.strptime(fecha_fin_str, '%Y-%m-%d').date()
                    pedidos_detalle = pedidos_detalle.filter(pedido__fecha__date__lte=fecha_fin)
                except ValueError:
                    pass # Ignorar si el formato de fecha es incorrecto


            cancelados_detalle = pedidos_detalle.filter(pedido__estado=0)
            pedidos_detalle = pedidos_detalle.exclude(pedido__estado=0)

            # Consultar cancelaciones desde Pedido directamente. Antes se
            # partía de DetallePedido: pedidos cancelados sin detalle desaparecían.
            pedidos_cancelados = (
                Pedido.objects.filter(estado=0)
                .select_related('usuario')
                .prefetch_related('detallepedido_set__producto')
                .order_by('-fecha_cancelacion', '-fecha', '-id')
            )
            if usuario_filtro:
                pedidos_cancelados = pedidos_cancelados.filter(
                    Q(usuario__nombres__icontains=usuario_filtro) |
                    Q(usuario__apellidos__icontains=usuario_filtro)
                )
            if fecha_inicio_str:
                try:
                    fecha_inicio = datetime.strptime(fecha_inicio_str, '%Y-%m-%d').date()
                    pedidos_cancelados = pedidos_cancelados.filter(fecha__date__gte=fecha_inicio)
                except ValueError:
                    pass
            if fecha_fin_str:
                try:
                    fecha_fin = datetime.strptime(fecha_fin_str, '%Y-%m-%d').date()
                    pedidos_cancelados = pedidos_cancelados.filter(fecha__date__lte=fecha_fin)
                except ValueError:
                    pass
            # NUEVO: las alertas de Cocina son incidencias, no cancelaciones.
            # Se muestran en una sección separada para que administración decida.
            incidencias_cocina = (
                EstadoPedidoCocina.objects.filter(
                    estado='alerta', pedido__estado=1
                )
                .select_related('pedido__usuario')
                .prefetch_related('pedido__detallepedido_set__producto')
                .order_by('-actualizado_en', '-pedido_id')
            )
            if usuario_filtro:
                incidencias_cocina = incidencias_cocina.filter(
                    Q(pedido__usuario__nombres__icontains=usuario_filtro) |
                    Q(pedido__usuario__apellidos__icontains=usuario_filtro)
                )
            if fecha_inicio_str:
                try:
                    fecha_inicio = datetime.strptime(fecha_inicio_str, '%Y-%m-%d').date()
                    incidencias_cocina = incidencias_cocina.filter(pedido__fecha__date__gte=fecha_inicio)
                except ValueError:
                    pass
            if fecha_fin_str:
                try:
                    fecha_fin = datetime.strptime(fecha_fin_str, '%Y-%m-%d').date()
                    incidencias_cocina = incidencias_cocina.filter(pedido__fecha__date__lte=fecha_fin)
                except ValueError:
                    pass

            datos = {
                'nombre': nombre_logeado,
                'pedido': pedidos_detalle,
                'pedido_cancelado': cancelados_detalle,
                'pedidos_cancelados': pedidos_cancelados,
                'incidencias_cocina': incidencias_cocina,
            }
            
            return render(request, "Historial.html", datos)
        
        else:

            datos = {'error': 1}
            return render(request, 'index.html', datos)
    else:
        datos = {'error': 0}
        return render(request, 'index.html', datos)
    
def mostrarUsuarios(request):

    estadoSesion = request.session.get('estadoSesion')
    rol = request.session.get('rol')


    if estadoSesion == True:
        if rol == 'Admin':

            nombre = request.session.get('usuarioLogeado')
            usu = Usuario.objects.all().values()

            datos = {
                'usu':usu,
                'nombre': nombre
            }
            
            return render(request, "Usuarios.html", datos)
        
        else:

            datos = {'error': 1}
            return render(request, 'index.html', datos)
    else:
        datos = {'error': 0}
        return render(request, 'index.html', datos)
    
def _calidad_mensual(pedidos):
    listo_sin_alerta = Q(estado=1, estado_cocina__estado='listo', estado_cocina__tuvo_problema=False)
    con_alerta = Q(estado_cocina__tuvo_problema=True) | Q(estado_cocina__estado='alerta')
    meses = (
        pedidos.annotate(mes=TruncMonth('fecha'))
        .values('mes')
        .annotate(
            finalizados=Count('pk', filter=listo_sin_alerta, distinct=True),
            con_problemas=Count('pk', filter=con_alerta, distinct=True),
        )
        .order_by('mes')
    )
    resultados = []
    for fila in meses:
        total_evaluados = fila['finalizados'] + fila['con_problemas']
        fila['tasa_problemas'] = fila['con_problemas'] * 100 / total_evaluados if total_evaluados else None
        resultados.append(fila)
    return resultados


def _formato_duracion_atencion(segundos):
    minutos, resto = divmod(round(segundos), 60)
    return f'{minutos} min {resto:02d} s'


def _atencion_mensual(pedidos):
    mediciones = Pedido.objects.filter(
        pk__in=pedidos.values('pk'), duracion_atencion_segundos__isnull=False
    )
    extra_por_pedido = Case(
        When(duracion_atencion_segundos__gt=REFERENCIA_ATENCION_SEGUNDOS,
             then=F('duracion_atencion_segundos') - REFERENCIA_ATENCION_SEGUNDOS),
        default=Value(0),
        output_field=IntegerField(),
    )
    meses = (
        mediciones.annotate(mes=TruncMonth('fecha'))
        .values('mes')
        .annotate(
            medidos=Count('pk'),
            promedio=Avg('duracion_atencion_segundos'),
            extra_promedio=Avg(extra_por_pedido),
            dentro_limite=Count('pk', filter=Q(duracion_atencion_segundos__lte=LIMITE_ATENCION_SEGUNDOS)),
        )
        .order_by('mes')
    )
    resultados = []
    for fila in meses:
        fila['promedio'] = _formato_duracion_atencion(fila['promedio'])
        fila['extra_promedio'] = _formato_duracion_atencion(fila['extra_promedio'])
        fila['sobre_limite'] = fila['medidos'] - fila['dentro_limite']
        fila['porcentaje_dentro'] = fila['dentro_limite'] * 100 / fila['medidos']
        resultados.append(fila)
    return resultados



def _atencion_por_vendedor(pedidos, vendedor_id=None):
    """Agrupa los pedidos medidos por mes y por la cuenta que registró el pedido.

    Los pedidos se identifican por PK para impedir duplicados si el filtro de
    productos genera varias coincidencias en DetallePedido.
    """
    mediciones = Pedido.objects.filter(
        pk__in=pedidos.values('pk'),
        duracion_atencion_segundos__isnull=False,
    )
    if vendedor_id:
        mediciones = mediciones.filter(usuario_id=vendedor_id)

    extra_por_pedido = Case(
        When(duracion_atencion_segundos__gt=REFERENCIA_ATENCION_SEGUNDOS,
             then=F('duracion_atencion_segundos') - REFERENCIA_ATENCION_SEGUNDOS),
        default=Value(0),
        output_field=IntegerField(),
    )
    grupos = (
        mediciones.annotate(mes=TruncMonth('fecha'))
        .values('mes', 'usuario_id', 'usuario__nombres', 'usuario__apellidos', 'usuario__usuario')
        .annotate(
            medidos=Count('pk'),
            promedio=Avg('duracion_atencion_segundos'),
            extra_promedio=Avg(extra_por_pedido),
            dentro_limite=Count('pk', filter=Q(duracion_atencion_segundos__lte=LIMITE_ATENCION_SEGUNDOS)),
        )
        .order_by('mes', 'usuario__apellidos', 'usuario__nombres', 'usuario_id')
    )
    resultados = []
    for fila in grupos:
        nombre = f"{fila['usuario__nombres'] or ''} {fila['usuario__apellidos'] or ''}".strip()
        fila['vendedor'] = nombre or fila['usuario__usuario'] or 'Usuario sin nombre'
        fila['promedio'] = _formato_duracion_atencion(fila['promedio'])
        fila['extra_promedio'] = _formato_duracion_atencion(fila['extra_promedio'])
        fila['sobre_limite'] = fila['medidos'] - fila['dentro_limite']
        fila['porcentaje_dentro'] = fila['dentro_limite'] * 100 / fila['medidos']
        resultados.append(fila)
    return resultados


def mostrarEstadisticas(request):
    pedidos_filtrados = Pedido.objects.all()
    filtro_producto = request.GET.get("producto")
    filtro_mes = request.GET.get("mes")
    filtro_anio = request.GET.get("anio")

    if filtro_producto:
        pedidos_filtrados = pedidos_filtrados.filter(detallepedido__producto__id=filtro_producto)
    if filtro_mes:
        pedidos_filtrados = pedidos_filtrados.filter(fecha__month=filtro_mes)
    if filtro_anio:
        pedidos_filtrados = pedidos_filtrados.filter(fecha__year=filtro_anio)

    pedidos = (
        pedidos_filtrados.exclude(estado=0)
        .select_related('usuario')
        .prefetch_related('detallepedido_set__producto')
    )

    # El filtro de vendedor afecta SOLO la tabla de tiempo por vendedor.
    # Mantiene intactas las ventas, encuestas, calidad y promedios generales.
    vendedores_con_mediciones = Usuario.objects.filter(
        rut__in=Pedido.objects.filter(
            pk__in=pedidos.values('pk'),
            duracion_atencion_segundos__isnull=False,
        ).values('usuario_id')
    ).order_by('nombres', 'apellidos', 'rut')
    vendedores_atencion = [
        {
            'id': v.rut,
            'nombre': (f'{v.nombres or ""} {v.apellidos or ""}'.strip() or v.usuario),
        }
        for v in vendedores_con_mediciones
    ]
    vendedor_seleccionado = request.GET.get('vendedor_tiempo', '').strip()
    if vendedor_seleccionado not in {v['id'] for v in vendedores_atencion}:
        vendedor_seleccionado = ''

    # ======== CÁLCULOS ========
    total_pedidos = pedidos.count()

    total_productos = sum(
        detalle.cantidad 
        for pedido in pedidos 
        for detalle in pedido.detallepedido_set.all()
    )

    promedio_pedidos_diarios = total_pedidos  # si quieres lo ajustamos después

    suma_total = sum(pedido.total for pedido in pedidos)

    calificaciones = dict(
        EncuestaSatisfaccion.objects.filter(
            pedido_id__in=pedidos.values('pk'), calificacion__isnull=False
        )
        .values_list('calificacion')
        .annotate(cantidad=Count('pk'))
    )
    total_respuestas = sum(calificaciones.values())
    escala = EncuestaSatisfaccion.Calificacion
    respuestas_positivas = sum(
        calificaciones.get(nota, 0)
        for nota in (escala.SATISFECHO, escala.MUY_SATISFECHO)
    )
    porcentaje_satisfaccion = respuestas_positivas * 100 / total_respuestas if total_respuestas else 0
    distribucion_satisfaccion = [
        {
            'nota': nota,
            'etiqueta': etiqueta,
            'cantidad': calificaciones.get(nota, 0),
            'porcentaje': calificaciones.get(nota, 0) * 100 / total_respuestas if total_respuestas else 0,
        }
        for nota, etiqueta in reversed(escala.choices)
    ]

    # ======== Suma por producto ========
    suma_por_producto = {}
    for pedido in pedidos:
        for detalle in pedido.detallepedido_set.all():
            nombre = detalle.producto.nombre
            subtotal = detalle.precio * detalle.cantidad
            suma_por_producto[nombre] = suma_por_producto.get(nombre, 0) + subtotal

    # ======== Evolución mensual ========
    evolucion_mensual = (
        pedidos.annotate(mes=TruncMonth("fecha"))
        .values("mes")
        .annotate(total=Sum("total"))
        .order_by("mes")
    )

    # Para cargar selects
    productos = Producto.objects.all()
    meses = range(1, 13)
    años = Pedido.objects.values_list("fecha__year", flat=True).distinct()

    datos = {
        "pedidos": pedidos,
        "total_pedidos": total_pedidos,
        "promedio_productos": promedio_pedidos_diarios,
        "total_respuestas": total_respuestas,
        "porcentaje_satisfaccion": porcentaje_satisfaccion,
        "distribucion_satisfaccion": distribucion_satisfaccion,
        "suma_total": suma_total,
        "suma_por_producto": suma_por_producto,
        "evolucion_mensual": evolucion_mensual,
        "calidad_mensual": _calidad_mensual(pedidos_filtrados),
        "atencion_mensual": _atencion_mensual(pedidos),
        "atencion_por_vendedor": _atencion_por_vendedor(pedidos, vendedor_seleccionado),
        "vendedores_atencion": vendedores_atencion,
        "vendedor_seleccionado": vendedor_seleccionado,
        "referencia_atencion_min": REFERENCIA_ATENCION_SEGUNDOS // 60,
        "limite_atencion_min": LIMITE_ATENCION_SEGUNDOS // 60,
        "productos": productos,
        "meses": meses,
        "anios": años,
    }

    return render(request, "Estadisticas.html", datos)



# ===  ===  ===  ===  ===  ===  === 
# FIN MENU ADMIN
# ===  ===  ===  ===  ===  ===  === 



# ===  ===  ===  ===  ===  ===  === 
# GESTION DE SESIONES
# ===  ===  ===  ===  ===  ===  === 

@never_cache
def iniciarSesion(request):
    if request.method != 'POST':
        return render(request, 'Index.html', {'error': 4})

    u = (request.POST.get('username') or '').strip()
    p = request.POST.get('password') or ''
    cuenta = Usuario.objects.filter(usuario=u).first()
    if cuenta is None:
        return render(request, 'Index.html', {'error': 5})

    valida = check_password(p, cuenta.password)
    if not valida:
        # Compatibilidad transitoria si alguien aún no ejecutó la migración.
        # En el primer acceso correcto se reemplaza por un hash seguro.
        es_legacy = not cuenta.password.startswith(('pbkdf2_', 'argon2$', 'bcrypt', 'scrypt$'))
        valida = es_legacy and constant_time_compare(p, cuenta.password)
        if valida:
            cuenta.password = make_password(p)
            cuenta.save(update_fields=['password'])

    if not valida:
        return render(request, 'Index.html', {'error': 3})

    # Evita reutilizar una sesión anterior.
    request.session.flush()
    request.session['estadoSesion'] = True
    request.session['rol'] = cuenta.rol
    request.session['rut'] = cuenta.rut
    request.session['usuarioLogeado'] = cuenta.nombres.upper()
    request.session['complejidad'] = cuenta.complejidad
    if cuenta.rol == 'Admin':
        return redirect('menuAdmin')
    if cuenta.rol == 'Cocina':
        return redirect('menuCocina')
    if cuenta.complejidad == 'Media':
        return redirect('menu2', opcion=3)
    return redirect('menu', opcion=1)

@never_cache
def cerrarSesion(request):
    # Borra absolutamente todos los datos de sesión (incluye carrito y permisos).
    request.session.flush()
    return redirect('inicio')


def _imagen_sin_duplicados(imagen):
    """Almacena una sola copia de cada imagen idéntica por contenido.

    Busca en todo MEDIA_ROOT/productos, incluso archivos que aún no están
    asociados a un Producto. No cambia los nombres guardados en la BD.
    """
    if not imagen:
        return None

    extensiones = {'.jpg', '.jpeg', '.png', '.webp', '.gif'}
    ext = Path(imagen.name).suffix.lower()
    if ext not in extensiones:
        raise ValueError('Solo se admiten imágenes JPG, PNG, WEBP o GIF.')

    digest = hashlib.sha256()
    for bloque in imagen.chunks():
        digest.update(bloque)
    imagen.seek(0)
    huella = digest.hexdigest()

    # Django FileField puede recibir una ruta de almacenamiento como string:
    # evita que Product.save vuelva a subir el archivo.
    carpeta = 'productos'
    try:
        _subcarpetas, archivos = default_storage.listdir(carpeta)
    except (FileNotFoundError, OSError):
        archivos = []

    for archivo in sorted(archivos):
        ruta_existente = f'{carpeta}/{archivo}'
        try:
            if default_storage.size(ruta_existente) != imagen.size:
                continue
            hash_existente = hashlib.sha256()
            with default_storage.open(ruta_existente, 'rb') as guardado:
                for bloque in iter(lambda: guardado.read(1024 * 1024), b''):
                    hash_existente.update(bloque)
            if hash_existente.hexdigest() == huella:
                return ruta_existente
        except (OSError, ValueError):
            continue

    ruta = f'{carpeta}/{huella}{ext}'
    if default_storage.exists(ruta):
        return ruta
    return default_storage.save(ruta, imagen)

def registrarProducto(request):
    
    estadoSesion = request.session.get('estadoSesion')
    rol = request.session.get('rol')

    if estadoSesion == True:

        if rol == 'Admin':

            if request.method == 'POST':

                nombre = request.POST.get('nombre')
                descripcion = request.POST.get('descripcion')
                precio = request.POST.get('precio')
                imagen = request.FILES.get('imagen')
                categoria = request.POST.get('categoria')

                # Aqui ya deberia guardarse en la base de datos
                try:
                    ruta_imagen = _imagen_sin_duplicados(imagen)
                except ValueError as exc:
                    messages.error(request, str(exc))
                    return redirect('menuPedidos')
                pro = Producto(nombre=nombre, descripcion=descripcion, precio=precio, imagen=ruta_imagen, categoria=categoria)
                pro.save()

                # Post/Redirect/Get: actualizar la página ya no vuelve a enviar
                # el formulario ni a crear otro producto o cargar otra imagen.
                messages.success(request, 'Producto registrado correctamente.')
                return redirect('menuPedidos')

            else:
                datos = {
                    'error': 2
                }
                return render(request, 'Pedido.html', datos)
        else:
            datos = {
                'error': 1 
            }
            return render(request, 'Index.html', datos)
    else:
        datos = {
            'error': 0
        }
        return render(request,'Index.html', datos)
    
def modificar_producto(request, id):
    estadoSesion = request.session.get('estadoSesion')
    rol = request.session.get('rol')

    if estadoSesion and rol == 'Admin':
        # Intenta obtener el producto o devuelve 404
        try:
            producto = Producto.objects.get(id=id)
        except Producto.DoesNotExist:
            return redirect('menuPedidos') # Si no existe, vuelve a la lista

        if request.method == 'POST':
            # 1. Recoger y actualizar datos del formulario
            producto.categoria = request.POST.get('categoria')
            producto.nombre = request.POST.get('nombre')
            producto.descripcion = request.POST.get('descripcion')
            producto.precio = request.POST.get('precio')

            # 2. Manejar la imagen (solo si se sube una nueva)
            nueva_imagen = request.FILES.get('imagen')
            if nueva_imagen:
                # Opcional: Si quieres borrar la imagen vieja del disco antes de actualizar, 
                # necesitas el paquete 'storages' o una lógica custom.
                try:
                    producto.imagen = _imagen_sin_duplicados(nueva_imagen)
                except ValueError as exc:
                    messages.error(request, str(exc))
                    return redirect('menuPedidos')
            
            # 3. Guardar los cambios
            producto.save()
            
            nombre = request.session.get('usuarioLogeado')
            pro = Producto.objects.all().values()
            datos = {
                'pro': pro,
                'nombre': nombre,
                'proceso': 1,
                'procesoNombre':'Modificado',
            }

            return render(request, 'Pedido.html', datos)

        # Si se accede por GET, simplemente redirige de vuelta
        return redirect('menuPedidos')
    else:
        # Manejo de errores de sesión/rol
        datos = {'error': 1} if estadoSesion else {'error': 0}
        return render(request, 'Index.html', datos)    
    
def eliminarProducto(request, id):
    estadoSesion = request.session.get('estadoSesion')
    rol = request.session.get('rol')

    if estadoSesion == True:
        if rol == 'Admin':
            pro = Producto.objects.get(id = id)
            pro.delete()

            nombre = request.session.get('usuarioLogeado')
            pro = Producto.objects.all().values()
            datos = {
                'pro': pro,
                'nombre': nombre,
                'proceso': 1,
                'procesoNombre':'Eliminado',
            }

            return render(request, 'Pedido.html', datos)
        else:
            datos = {
                'error': 1 
            }
            return render(request, 'Index.html', datos)
    else:
        datos = {
            'error': 0
        }
        return render(request,'Index.html', datos)

# ===  ===  ===  ===  ===  ===  === 
#CRUD USUARIOS
# ===  ===  ===  ===  ===  ===  ===

def agregarUsuario(request):
    estadoSesion = request.session.get('estadoSesion')
    rol = request.session.get('rol')

    if estadoSesion is not True:
        return render(request, 'Index.html', {'error': 0})
    if rol != 'Admin':
        return render(request, 'Index.html', {'error': 1})
    if request.method != 'POST':
        return render(request, 'Usuarios.html', {'error': 2,
                                                'usu': Usuario.objects.all(),
                                                'nombre': request.session.get('usuarioLogeado')})

    rut = (request.POST.get('rut') or '').strip()
    usuarioObj = (request.POST.get('usuario') or '').strip()
    nombres = (request.POST.get('nombres') or '').strip()
    apellidos = (request.POST.get('apellidos') or '').strip()
    rolUsuario = (request.POST.get('rol') or '').strip()
    password = request.POST.get('password') or ''
    complejidad = request.POST.get('complejidad') or ''

    def respuesta_error(codigo):
        return render(request, 'Usuarios.html', {
            'error': codigo,
            'usu': Usuario.objects.all(),
            'nombre': request.session.get('usuarioLogeado'),
        })

    if not rut or len(rut) > 12 or not usuarioObj or not password:
        return respuesta_error(9)

    # Comparar tanto el RUT original como variantes con puntos o guion.
    # No cambia el RUT guardado en tus registros anteriores.
    rut_normalizado = re.sub(r'[^0-9K]', '', rut.upper())
    if not rut_normalizado:
        return respuesta_error(9)

    if Usuario.objects.filter(rut__iexact=rut).exists():
        return respuesta_error(7)

    if any(
        re.sub(r'[^0-9K]', '', str(actual).upper()) == rut_normalizado
        for actual in Usuario.objects.values_list('rut', flat=True)
    ):
        return respuesta_error(7)

    # La pantalla de login busca una cuenta por el campo 'usuario'.
    # Impedir que dos personas compartan ese identificador de acceso.
    if Usuario.objects.filter(usuario__iexact=usuarioObj).exists():
        return respuesta_error(8)

    try:
        with transaction.atomic():
            usu = Usuario(
                rut=rut, usuario=usuarioObj, nombres=nombres,
                apellidos=apellidos, rol=rolUsuario,
                password=make_password(password), complejidad=complejidad,
            )
            # MUY IMPORTANTE: una inserción nueva, no .save() que sobrescribe
            # la fila existente si rut ya es su clave primaria.
            usu.save(force_insert=True)
    except IntegrityError:
        return respuesta_error(7)

    return render(request, 'Usuarios.html', {
        'proceso': 1,
        'procesoNombre': 'agregado',
        'usu': Usuario.objects.all(),
        'nombre': request.session.get('usuarioLogeado'),
    })

def eliminarUsuario(request, rut):
    estadoSesion = request.session.get('estadoSesion')
    rol = request.session.get('rol')

    if estadoSesion == True:
        if rol == 'Admin':

            usu = Usuario.objects.get(rut = rut)
            

            if usu.rol == 'Admin':

                usu = Usuario.objects.all().values()
                nombre = request.session.get('usuarioLogeado')
                datos = {
                    'error': 6,
                    'usu':usu,
                    'nombre': nombre,
                }
                return render(request, 'Usuarios.html', datos)
            else:
                usu.delete()
                nombre = request.session.get('usuarioLogeado')
                usu = Usuario.objects.all().values()
                datos = {
                    'proceso': 1,
                    'procesoNombre':'eliminado',
                    'usu':usu,
                    'nombre': nombre,
                }
                return render(request, 'Usuarios.html', datos)

        else:
            datos = {
                'error': 1 
            }
            return render(request, 'Index.html', datos)
    else:
        datos = {
            'error': 0
        }
        return render(request,'Index.html', datos)


def editarUsuario(request, rut):
    # 1. Verificar la sesión y el rol (similar a otras funciones de administrador)
    estadoSesion = request.session.get('estadoSesion')
    rol = request.session.get('rol')

    if estadoSesion and rol == 'Admin':
        # 2. Obtener el usuario a editar o devolver 404 si no existe
        # Nota: La implementación de 'get_object_or_404' no está en tu import, pero es lo estándar
        # Usaré el método .get() para ser consistente con tu código existente.
        try:
            usu = Usuario.objects.get(rut=rut)
        except Usuario.DoesNotExist:
            # Manejo de error si el usuario no existe (opcional)
            return redirect('usuarios') # Redirigir a la lista si no se encuentra

        # 3. Procesar la solicitud POST (Guardar la edición)
        if request.method == 'POST':
            # Comprobar que el nuevo nombre de acceso no pertenezca a otra cuenta.
            usuario_nuevo = (request.POST.get('usuario') or '').strip()
            if not usuario_nuevo:
                return render(request, 'Usuarios.html', {
                    'error': 9, 'usu': Usuario.objects.all(),
                    'nombre': request.session.get('usuarioLogeado'),
                })
            if Usuario.objects.filter(usuario__iexact=usuario_nuevo).exclude(rut=rut).exists():
                return render(request, 'Usuarios.html', {
                    'error': 8, 'usu': Usuario.objects.all(),
                    'nombre': request.session.get('usuarioLogeado'),
                })
            # Obtener datos del formulario
            usu.usuario = usuario_nuevo
            usu.nombres = request.POST.get('nombres')
            usu.apellidos = request.POST.get('apellidos')
            usu.rol = request.POST.get('rol')
            usu.complejidad = request.POST.get('complejidad')
            
            # Solo actualizar la contraseña si se proporciona una nueva
            nueva_password = request.POST.get('password')
            if nueva_password:
                usu.password = make_password(nueva_password) # Nunca almacenar texto plano

            usu.save() # Guardar los cambios en la base de datos
            nombre = request.session.get('usuarioLogeado')
            usu = Usuario.objects.all().values()
            datos = {
                'proceso': 1,
                'procesoNombre':'modificado',
                'usu':usu,
                'nombre': nombre,
            }
            return render(request, 'Usuarios.html', datos) # Redirigir a la lista de usuarios después de guardar

        # 4. Procesar la solicitud GET (Mostrar el formulario de edición)
        nombre_logeado = request.session.get('usuarioLogeado')
        datos = {
            'usuario_a_editar': usu, # Pasar el objeto usuario al template
            'nombre': nombre_logeado
        }
        # Nota: Aquí se necesitaría un template llamado 'EditarUsuario.html' o similar, 
        # o reutilizar 'Usuarios.html' con lógica condicional.
        return render(request, 'Usuarios.html', datos) # Asumiendo que reutilizarás Usuarios.html con los datos del usuario.

    else:
        # Manejo de errores de sesión/rol (consistente con tu código)
        datos = {'error': 1} if estadoSesion else {'error': 0}
        return render(request, 'Index.html', datos)
    
def verUsuario(request, rut):
    estadoSesion = request.session.get('estadoSesion')
    rol = request.session.get('rol')

    if estadoSesion and rol == 'Admin':
        try:
            usu = Usuario.objects.get(rut=rut)
        except Usuario.DoesNotExist:
            return redirect('usuarios')

        nombre_logeado = request.session.get('usuarioLogeado')
        datos = {
            'usuario_a_ver': usu, # Nombre diferente para el template de visualización si tuvieras uno dedicado
            'nombre': nombre_logeado
        }
        # Renderizar un template 'VerUsuario.html' o similar
        return render(request, 'Usuarios.html', datos) # Usaremos el mismo template por simplicidad.
    else:
        datos = {'error': 1} if estadoSesion else {'error': 0}
        return render(request, 'Index.html', datos)

# ===  ===  ===  ===  === 
# Carrito
# ===  ===  ===  ===  === 
def agregar_carrito(request, producto_id):
    carrito = request.session.get('carrito', {})
    producto = Producto.objects.get(id=producto_id)

    # obtener la cantiadda ddesde el formulario
    cantidad = int(request.POST.get('cantidad', 1))
    if not carrito and request.method == 'POST' and cantidad > 0:
        _iniciar_atencion(request)

    # calculo total
    total = sum(item["precio"] * item["cantidad"] for item in carrito.values())


    #si ya existe en el carrito, solo aumentar cantidad
    if str(producto_id) in carrito:
        carrito[str(producto_id)]['cantidad'] += cantidad

    # subtotal
    # for key, item in carrito.items():
    #     item["subtotal"] = item["precio"] * item["cantidad"]


    else:
        carrito[str(producto_id)] = {
            "nombre": producto.nombre,
            "precio": producto.precio,
            "cantidad": cantidad,
            "total": total  
        }
    request.session['carrito'] = carrito
    return redirect(request.META.get("HTTP_REFERER", "menu"))

def eliminar_del_carrito(request, producto_id):
    carrito = request.session.get("carrito", {})

    # Si el producto está en el carrito, eliminarlo
    if str(producto_id) in carrito:
        del carrito[str(producto_id)]

    request.session["carrito"] = carrito
    return redirect(request.META.get("HTTP_REFERER", "menu"))
    
def vaciar_carrito(request):
    _cerrar_carrito(request)
    return redirect(request.META.get("HTTP_REFERER", "menu"))
def vaciar_carrito2(request):
    _cerrar_carrito(request)
    return redirect(request.META.get("HTTP_REFERER", "menu2"))

def finalizar(request):
    
    usuario_nombre = request.session.get("usuarioLogeado")
    usu_db = Usuario.objects.filter(nombres=usuario_nombre).first()
    
    if not usu_db:
        # Redirección si el usuario no está encontrado
        return redirect("menu") 
        
    carrito = request.session.get("carrito", {})
    
    if not carrito:
        # Redirección si el carrito está vacío
        return redirect("/menu/1") 

    # --- INICIO DE LÓGICA DE CÁLCULO DE PROPINAS ---
    
    # 1. Capturar el porcentaje de propina del formulario HTML
    # Viene del campo oculto <input type="hidden" name="propina_porcentaje"> (o similar)
    propina_porcentaje_str = request.POST.get("propina_porcentaje", "0.00")
    
    # Capturar el método de pago
    tipo_pago_seleccionado = request.POST.get("tipoPago", "Efectivo") 

    # 2. Calcular el subtotal de los productos (Base para el cálculo de la propina)
    subtotal_productos = sum(item["precio"] * item["cantidad"] for item in carrito.values())
    
    # 3. Convertir el porcentaje de propina a float y calcular el monto
    try:
        propina_porcentaje = float(propina_porcentaje_str)
    except ValueError:
        propina_porcentaje = 0.00
        
    propina_monto = subtotal_productos * propina_porcentaje
    
    # 4. Calcular el Total Final (Subtotal + Propina) para guardar en la DB
    total_final_con_propina = subtotal_productos + propina_monto
    
    # 🔑 Se reemplaza la variable 'total' original por el nuevo cálculo
    total_a_guardar = total_final_con_propina

    # --- FIN DE LÓGICA DE CÁLCULO DE PROPINAS ---

    # Crear el pedido
    pedido = Pedido.objects.create(
        usuario=usu_db,
        fecha=timezone.now(),
        # USAMOS EL TIPO DE PAGO CAPTURADO
        tipoPago=tipo_pago_seleccionado, 
        # 🔑 AJUSTE: Guardar el total final CON PROPINA
        total=total_a_guardar,
        estado=1,
        duracion_atencion_segundos=_segundos_atencion(request),
    )
    
    # Crear detalles del pedido (ESTO NO CAMBIA)
    for key, item in carrito.items():
        DetallePedido.objects.create(
            pedido=pedido,
            producto=Producto.objects.get(id=int(key)),
            cantidad=item["cantidad"],
            precio=item["precio"],
        )

    # Vaciar carrito (ESTO NO CAMBIA)
    _cerrar_carrito(request)

    opcion = 1

    # Lógica de filtrado de productos y cálculo de totales para el re-renderizado (ESTO NO CAMBIA)
    if opcion == 1:
        pro = Producto.objects.filter(categoria='Almuerzo')
    elif opcion == 2:
        pro = Producto.objects.filter(categoria='Sopa')
    elif opcion == 3:
        pro = Producto.objects.filter(categoria='Bebida')
    elif opcion == 4:
        pro = Producto.objects.filter(categoria='Postre')
    elif opcion == 5:
        pro = Producto.objects.filter(categoria='Salado')

    nombre = request.session.get('usuarioLogeado')
    carrito = request.session.get('carrito', {})
    total = sum(item["precio"] * item["cantidad"] for item in carrito.values()) 

    datos = {
        'pro': pro,
        'nombre': nombre,
        'opcion': opcion,
        'carrito': carrito,
        'total': total,
        
        'proceso':1,
        'procesoNombre':'ingresado'
    }
    
    return render(request, "Menu.html", datos)

def _generar_qr_encuesta(request, codigo):
    ruta = reverse('responder_encuesta', args=[codigo])
    url = (
        f'{settings.ENCUESTA_BASE_URL}{ruta}'
        if settings.ENCUESTA_BASE_URL
        else request.build_absolute_uri(ruta)
    )
    with BytesIO() as archivo:
        qrcode.make(url, box_size=8, border=4, error_correction=qrcode.constants.ERROR_CORRECT_M).save(archivo)
        return b64encode(archivo.getvalue()).decode('ascii')


@require_POST
def finalizar2(request):
    usuario = Usuario.objects.filter(pk=request.session.get('rut')).first()
    if not usuario:
        return redirect('inicio')

    carrito = request.session.get('carrito', {})
    if not carrito:
        return redirect('menu2', opcion=1)

    subtotal = sum(item['precio'] * item['cantidad'] for item in carrito.values())
    porcentajes = {'0.05': 5, '0.1': 10, '0.10': 10, '0.15': 15}
    porcentaje = porcentajes.get(request.POST.get('propina_porcentaje'), 0)
    propina = (subtotal * porcentaje + 50) // 100
    tipo_pago = request.POST.get('tipoPago', 'Efectivo')

    with transaction.atomic():
        pedido = Pedido.objects.create(
            usuario=usuario, fecha=timezone.now(), tipoPago=tipo_pago,
            total=subtotal + propina, estado=1,
            duracion_atencion_segundos=_segundos_atencion(request),
        )
        lineas = []
        for clave, item in carrito.items():
            producto_id = item.get('producto_id_real') or clave.split('_', 1)[0]
            producto = get_object_or_404(Producto, pk=producto_id)
            DetallePedido.objects.create(
                pedido=pedido, producto=producto,
                cantidad=item['cantidad'], precio=item['precio'],
            )
            lineas.append({
                'nombre': producto.nombre,
                'cantidad': item['cantidad'],
                'importe': item['precio'] * item['cantidad'],
            })
        encuesta = EncuestaSatisfaccion.objects.create(pedido=pedido)
        qr_encuesta = _generar_qr_encuesta(request, encuesta.codigo)

    _cerrar_carrito(request)
    datos = {
        'pro': Producto.objects.filter(categoria='Almuerzo'),
        'nombre': request.session.get('usuarioLogeado'),
        'opcion': 1,
        'carrito': {},
        'total': 0,
        'proceso': 1,
        'procesoNombre': 'ingresado',
        'comanda': {
            'pedido': pedido,
            'lineas': lineas,
            'subtotal': subtotal,
            'propina': propina,
            'qr_encuesta': qr_encuesta,
        },
    }
    return render(request, 'Menu2.html', datos)


@require_GET
def vistaPreviaEncuesta(request):
    return render(request, 'EncuestaSatisfaccion.html', {
        'formulario': EncuestaSatisfaccionForm(),
        'nombre_vendedor': 'Vendedor de ejemplo',
        'vista_previa': True,
    })


@require_http_methods(['GET', 'POST'])
def responderEncuesta(request, codigo):
    plantilla = 'EncuestaSatisfaccion.html'
    encuesta = (
        EncuestaSatisfaccion.objects.filter(pk=codigo, pedido__estado=1)
        .select_related('pedido__usuario')
        .first()
    )
    if encuesta is None:
        return render(request, plantilla, {'no_disponible': True}, status=404)
    if encuesta.calificacion is not None:
        return render(request, plantilla, {'respondida': True})

    formulario = EncuestaSatisfaccionForm(request.POST if request.method == 'POST' else None)
    if request.method == 'POST' and formulario.is_valid():
        with transaction.atomic():
            # La cancelación del pedido usa el mismo bloqueo.
            pedido = Pedido.objects.select_for_update().filter(pk=encuesta.pedido_id, estado=1).first()
            if pedido is None:
                return render(request, plantilla, {'no_disponible': True}, status=404)
            EncuestaSatisfaccion.objects.filter(pk=codigo, calificacion__isnull=True).update(
                calificacion=formulario.cleaned_data['calificacion'],
                nombre_cliente=formulario.cleaned_data['nombre_cliente'],
            )
        return redirect('responder_encuesta', codigo=codigo)

    vendedor = encuesta.pedido.usuario
    nombre_vendedor = f'{vendedor.nombres.strip()} {vendedor.apellidos.strip()}'.strip()
    return render(request, plantilla, {
        'formulario': formulario,
        'nombre_vendedor': nombre_vendedor or 'Vendedor',
    })


def descargar_cartola(request):
    producto = request.GET.get("producto")
    mes = request.GET.get("mes")
    anio = request.GET.get("anio")

    filtros = {}

    if mes and mes != "-- Mes --":
        filtros["fecha__month"] = int(mes)

    if anio and anio != "-- Año --":
        filtros["fecha__year"] = int(anio)

    # Si filtra por producto, se usa DetallePedido
    if producto and producto != "-- Seleccionar --":
        filtros["detallepedido__producto__nombre"] = producto

    pedidos = Pedido.objects.filter(**filtros).order_by("fecha").distinct()

    # Crear Excel
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Cartola mensual"

    encabezados = ["Fecha", "Producto", "Cantidad", "Subtotal"]
    ws.append(encabezados)
    for col in range(1, 5):
        ws.cell(row=1, column=col).font = Font(bold=True)

    # Escribir detalles
    for pedido in pedidos:
        for det in pedido.detallepedido.all():
            if producto and producto != "-- Seleccionar --":
                if det.producto.nombre != producto:
                    continue

            ws.append([
                pedido.fecha.strftime("%d-%m-%Y"),
                det.producto.nombre,
                det.cantidad,
                det.subtotal
            ])

    total = pedidos.aggregate(total=Sum("total"))["total"] or 0
    ws.append(["", "", "TOTAL", total])

    response = HttpResponse(
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    response["Content-Disposition"] = f'attachment; filename="cartola_{mes}_{anio}.xlsx"'
    wb.save(response)
    return response

def historialVendedor(request):
    nombre = request.session.get('usuarioLogeado')
    rut = request.session.get('rut')

    pedidos_detalle =DetallePedido.objects.filter(pedido__usuario__rut=rut).select_related(
                'pedido__usuario', 
                'producto'
            ).order_by('-pedido__fecha') # Ordenar por fecha descendente
    


    cancelados_detalle = pedidos_detalle.filter(pedido__estado=0)
    pedidos_detalle = pedidos_detalle.exclude(pedido__estado=0)
    datos = {
        'nombre': nombre,
        'pedido': pedidos_detalle,
        'pedido_cancelado': cancelados_detalle,
    }
    return render(request, 'historialVendedor.html', datos)


# =============================================================
# NUEVA VISTA DE COCINA: menuCocina
# No se modifican variables ni vistas anteriores del proyecto.
# =============================================================

def _validar_usuario_cocina(request):
    """Valida el rol y la sesión que ya utiliza el proyecto original."""
    if request.session.get('estadoSesion') is not True:
        return None
    if request.session.get('rol') != 'Cocina':
        return None
    rut = request.session.get('rut')
    if not rut:
        return None
    return Usuario.objects.filter(rut=rut, rol='Cocina').first()


def _datos_pedido_cocina(pedido, estado_registrado=None):
    return {
        'id': pedido.id,
        'hora': pedido.fecha.strftime('%H:%M'),
        'vendedor': f'{pedido.usuario.nombres} {pedido.usuario.apellidos}'.strip(),
        'observacion': estado_registrado.observacion if estado_registrado else '',
        'productos': [
            {
                'nombre': detalle.producto.nombre,
                'cantidad': detalle.cantidad,
            }
            for detalle in pedido.detallepedido_set.all()
        ],
    }


@require_GET
def menuCocina(request):

    # Comprobar sesión iniciada
    estadoSesion = request.session.get('estadoSesion')
    rol = request.session.get('rol')
    rut = request.session.get('rut')

    if estadoSesion != True:
        return redirect('inicio')

    # Solo permitir acceso al rol Cocina
    if rol != 'Cocina':
        return HttpResponseForbidden(
            'Este menú es exclusivo para usuarios de Cocina.'
        )

    # Buscar el usuario registrado
    usuario_cocina = Usuario.objects.filter(
        rut=rut,
        rol='Cocina'
    ).first()

    if usuario_cocina is None:
        return HttpResponseForbidden(
            'No se encontró el usuario Cocina.'
        )

    nombre = request.session.get('usuarioLogeado')

    datos = {
        'nombre': nombre,
        'rol': rol
    }

    return render(request, 'menuCocina.html', datos)

@require_GET
@never_cache
def menuCocinaDatos(request):
    """Devuelve pedidos confirmados de hoy; no crea ni modifica registros."""
    if not _validar_usuario_cocina(request):
        return JsonResponse({'error': 'Acceso denegado.'}, status=403)

    hoy = datetime.now(ZoneInfo('America/Santiago')).date()  # USE_TZ=False en tu proyecto.
    pedidos = (
        Pedido.objects.filter(fecha__date=hoy, estado=1)
        .select_related('usuario', 'estado_cocina')
        .prefetch_related('detallepedido_set__producto')
        .order_by('fecha', 'id')
    )

    agrupados = {'pendientes': [], 'listos': [], 'alertas': []}
    for pedido in pedidos:
        # Un pedido sin registro en EstadoPedidoCocina es pendiente.
        # Así funcionan los pedidos guardados con la lógica actual.
        try:
            estado_registrado = pedido.estado_cocina
        except EstadoPedidoCocina.DoesNotExist:
            estado_registrado = None

        estado = estado_registrado.estado if estado_registrado else 'pendiente'
        categoria = {'pendiente': 'pendientes', 'listo': 'listos', 'alerta': 'alertas'}.get(estado, 'pendientes')
        agrupados[categoria].append(_datos_pedido_cocina(pedido, estado_registrado))

    return JsonResponse({
        'pedidos': agrupados,
        'resumen': {nombre: len(lista) for nombre, lista in agrupados.items()},
    })


@require_POST
def menuCocinaActualizar(request, pedido_id):
    """Guarda listo, alerta o vuelta a pendiente en la NUEVA tabla."""
    if not _validar_usuario_cocina(request):
        return JsonResponse({'error': 'Acceso denegado.'}, status=403)

    try:
        payload = json.loads(request.body.decode('utf-8'))
    except (ValueError, UnicodeDecodeError):
        return JsonResponse({'error': 'Datos JSON inválidos.'}, status=400)

    if not isinstance(payload, dict):
        return JsonResponse({'error': 'Formato inválido.'}, status=400)

    accion = payload.get('accion')
    observacion = payload.get('observacion', '')
    if accion not in ('listo', 'alerta', 'pendiente'):
        return JsonResponse({'error': 'Acción no permitida.'}, status=400)
    if not isinstance(observacion, str) or len(observacion) > 200:
        return JsonResponse({'error': 'Observación de máximo 200 caracteres.'}, status=400)
    observacion = observacion.strip()
    if accion == 'alerta' and not observacion:
        return JsonResponse({'error': 'Indica el motivo del problema.'}, status=400)

    hoy = datetime.now(ZoneInfo('America/Santiago')).date()
    with transaction.atomic():
        # Se bloquea el Pedido para evitar dos actualizaciones simultáneas.
        pedido = Pedido.objects.select_for_update().filter(
            pk=pedido_id, fecha__date=hoy, estado=1
        ).first()
        if pedido is None:
            return JsonResponse({'error': 'Pedido de hoy no encontrado.'}, status=404)

        registro, _ = EstadoPedidoCocina.objects.get_or_create(pedido=pedido)
        actual = registro.estado

        if accion in ('listo', 'alerta') and actual != 'pendiente':
            return JsonResponse({'error': 'Este pedido ya no está pendiente.'}, status=409)
        if accion == 'pendiente' and actual == 'pendiente':
            return JsonResponse({'error': 'Este pedido ya está pendiente.'}, status=409)

        registro.estado = accion
        registro.observacion = observacion if accion == 'alerta' else ''
        registro.tuvo_problema = registro.tuvo_problema or 'alerta' in (actual, accion)
        registro.save(update_fields=['estado', 'observacion', 'tuvo_problema', 'actualizado_en'])

    mensajes = {
        'listo': 'Pedido marcado como listo.',
        'alerta': 'Problema registrado en el pedido.',
        'pendiente': 'Pedido devuelto a preparación.',
    }
    return JsonResponse({
        'ok': True,
        'estado': accion,
        'mensaje': mensajes[accion],
    })


# =============================================
# CANCELACIONES (conserva detalle y motivo)
# =============================================
@require_POST
def cancelarCarrito(request):
    if request.session.get('estadoSesion') is not True:
        return redirect('inicio')
    if request.session.get('rol') not in ('Admin', 'Vendedor'):
        return HttpResponseForbidden('No tienes permisos para cancelar pedidos.')

    motivo = (request.POST.get('motivo_cancelacion') or '').strip()
    if not motivo or len(motivo) > 250:
        return HttpResponseForbidden('Es obligatorio indicar un motivo de hasta 250 caracteres.')

    carrito = request.session.get('carrito', {})
    if not carrito:
        return redirect('menu2', opcion=3)

    vendedor = get_object_or_404(Usuario, rut=request.session.get('rut'))
    # Validación previa para evitar un pedido sin detalles si algún producto fue borrado.
    items = []
    for key, item in carrito.items():
        producto_id = item.get('producto_id_real') or str(key).split('_')[0]
        producto = get_object_or_404(Producto, pk=producto_id)
        cantidad = int(item['cantidad'])
        if cantidad < 1:
            return HttpResponseForbidden('Cantidad inválida.')
        items.append((producto, cantidad, int(item['precio'])))

    with transaction.atomic():
        pedido = Pedido.objects.create(
            usuario=vendedor, fecha=timezone.now(), tipoPago='No realizado',
            total=sum(c * precio for _, c, precio in items), estado=0,
            motivo_cancelacion=motivo, fecha_cancelacion=timezone.now()
        )
        DetallePedido.objects.bulk_create([
            DetallePedido(pedido=pedido, producto=p, cantidad=c, precio=precio)
            for p, c, precio in items
        ])
    _cerrar_carrito(request)
    messages.success(request, f'Pedido cancelado #{pedido.pk} guardado con su motivo.')
    origen = request.POST.get('origen')
    return redirect('menu', opcion=1) if origen == 'menu' else redirect('menu2', opcion=3)


@require_POST
def cancelarPedidoRegistrado(request, pedido_id):
    if request.session.get('estadoSesion') is not True:
        return redirect('inicio')
    rol = request.session.get('rol')
    if rol not in ('Admin', 'Vendedor'):
        return HttpResponseForbidden('Sin permisos para cancelar pedidos.')
    motivo = (request.POST.get('motivo_cancelacion') or '').strip()
    if not motivo or len(motivo) > 250:
        return HttpResponseForbidden('Indica un motivo de hasta 250 caracteres.')

    with transaction.atomic():
        pedido = get_object_or_404(Pedido.objects.select_for_update(), pk=pedido_id)
        if rol != 'Admin' and pedido.usuario_id != request.session.get('rut'):
            return HttpResponseForbidden('Solo puedes cancelar tus propios pedidos.')
        if pedido.estado != 1:
            messages.error(request, 'Este pedido ya está cancelado.')
        else:
            # Un pedido terminado en cocina no debe cancelarse accidentalmente.
            estado_cocina = EstadoPedidoCocina.objects.filter(pedido=pedido).first()
            if estado_cocina and estado_cocina.estado == 'listo':
                messages.error(request, 'El pedido ya está listo en cocina; revisa con administración.')
            else:
                pedido.estado = 0
                pedido.motivo_cancelacion = motivo
                pedido.fecha_cancelacion = timezone.now()
                pedido.save(update_fields=['estado', 'motivo_cancelacion', 'fecha_cancelacion'])
                messages.success(request, f'Pedido #{pedido.pk} cancelado con motivo registrado.')

    return redirect('historial' if rol == 'Admin' else 'historialVendedor')
