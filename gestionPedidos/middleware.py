"""Protección de acceso y caché para las vistas propias de Café Tea Time.

El botón Atrás es una función del navegador; no se puede desactivar de forma
fiable. La seguridad es la sesión invalidada y la validación en el servidor.
"""
from django.http import HttpResponseForbidden
from django.shortcuts import redirect
from django.utils.cache import add_never_cache_headers


class ProteccionSesionMiddleware:
    PUBLICAS = {'/', '/login', '/login/', '/logout', '/logout/'}
    PREFIJOS_PUBLICOS = ('/admin/', '/static/', '/media/', '/encuesta/')
    PREFIJOS_ADMIN = (
        '/menuAdmin', '/menuPedidos', '/registrarProducto',
        '/modificarProducto/', '/eliminarProducto/', '/historial',
        '/usuarios', '/agregarUsuario', '/editarUsuario/',
        '/eliminarUsuario/', '/estadisticas', '/descargar-cartola/',
    )
    PREFIJOS_COCINA = ('/menuCocina/', '/menuCocina')

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        ruta = request.path_info
        if ruta not in self.PUBLICAS and not ruta.startswith(self.PREFIJOS_PUBLICOS):
            if request.session.get('estadoSesion') is not True or not request.session.get('rut'):
                respuesta = redirect('inicio')
                add_never_cache_headers(respuesta)
                return respuesta

            rol = request.session.get('rol')
            if ruta.startswith(self.PREFIJOS_COCINA) and rol != 'Cocina':
                return self._sin_permisos()
            if ruta.startswith(self.PREFIJOS_ADMIN) and not ruta.startswith('/historialVendedor') and rol != 'Admin':
                return self._sin_permisos()

        respuesta = self.get_response(request)
        # Impide guardar copias HTML privadas en cachés normales.
        # También obliga a revalidar al navegar por el historial.
        if not ruta.startswith(('/static/', '/media/')):
            add_never_cache_headers(respuesta)
            respuesta['Pragma'] = 'no-cache'
            respuesta['Expires'] = '0'
        return respuesta

    @staticmethod
    def _sin_permisos():
        respuesta = HttpResponseForbidden('No tienes permisos para entrar a esta sección.')
        add_never_cache_headers(respuesta)
        return respuesta
