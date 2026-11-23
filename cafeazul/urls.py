from django.contrib import admin
from django.urls import path

from gestionPedidos import views

#Configuracion de las imagenes
from django.conf import settings
from django.conf.urls.static import static


urlpatterns = [
    path('admin/', admin.site.urls),

    path('', views.mostrarIndex, name='inicio'),
    
    path('login', views.iniciarSesion),
    path('logout', views.cerrarSesion, name='cerrarSesion'),


    path('menu/<int:opcion>', views.mostrarMenu, name='menu'),
    path('agregar/<int:producto_id>', views.agregar_carrito, name='agregar_carrito'),
    path('vaciar/', views.vaciar_carrito, name='vaciar_carrito'),
    path('vaciar2/', views.vaciar_carrito, name='vaciar_carrito2'),
    path('vaciar3/', views.vaciar_carrito, name='vaciar_carrito3'),


    path('eliminar/<int:producto_id>/', views.eliminar_del_carrito, name='eliminar_del_carrito'),
    path('finalizar/', views.finalizar, name="finalizar"),
    path('finalizar2/', views.finalizar2, name="finalizar2"),
    path('finalizar3/', views.finalizar3, name="finalizar3"),



    # path('menu2/', views.mostrarMenu2, name='menu2'),   # Media complejidad
    # path('menu2/<int:opcion>', views.menu2, name="menu2"),
    # path('menu2/', views.menu2, {'opcion': 1}, name="menu2_default"),
    # path('menu3/', views.menu3, name='menu3_default'),
    path('menu2/', views.menu2, {'opcion': 1}, name="menu2_default"),
    path('menu2/<int:opcion>/', views.menu2, name='menu2'),
    path('menu2/atencion/', views.controlar_atencion, name='controlar_atencion'),


    path('menuAdmin', views.mostrarMenuAdmin, name='menuAdmin'),

    path('menuPedidos',views.mostrarPedido, name='menuPedidos'),
    # guardar productos en pedidos
    path('registrarProducto', views.registrarProducto, name='registrarProducto'),
    path('modificarProducto/<int:id>', views.modificar_producto, name='modificar_producto'),
    path('eliminarProducto/<int:id>', views.eliminarProducto, name='eliminarProducto'),


    path('historial', views.mostrarHistorial, name='historial'),
    path('historialVendedor/', views.historialVendedor, name='historialVendedor'),


    path('usuarios', views.mostrarUsuarios, name='usuarios'),
    # guardar usuarios en base de datos
    path('agregarUsuario', views.agregarUsuario, name='agregarUsuario'),
    path('eliminarUsuario/<str:rut>', views.eliminarUsuario, name='eliminarUsuario'),
    path('editarUsuario/<str:rut>', views.editarUsuario, name='editarUsuario'),



    path('estadisticas', views.mostrarEstadisticas, name='estadisticas'),
    path('estadisticas/encuesta/', views.vistaPreviaEncuesta, name='vista_previa_encuesta'),
    path('encuesta/<uuid:codigo>/', views.responderEncuesta, name='responder_encuesta'),

    #cartola
    path("descargar-cartola/", views.descargar_cartola, name="descargar_cartola"),



    path('agregar2/<int:producto_id>', views.agregar_carrito_menu2, name='agregar_carrito_menu2'),

    # NUEVAS RUTAS DE COCINA (no reemplazar las existentes)
    path('menuCocina/',views.menuCocina,name='menuCocina'),
    path('menuCocina/datos/', views.menuCocinaDatos, name='menuCocinaDatos'),
    path('menuCocina/pedido/<int:pedido_id>/estado/', views.menuCocinaActualizar, name='menuCocinaActualizar'),

    path('cancelar-carrito/', views.cancelarCarrito, name='cancelar_carrito'),
    path('cancelar-pedido/<int:pedido_id>/', views.cancelarPedidoRegistrado, name='cancelar_pedido'),

]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    

