"""Identifica archivos de imagen idénticos en media/productos/, sin afectar pedidos."""
import hashlib
from collections import defaultdict
from pathlib import Path
from django.conf import settings
from django.core.management.base import BaseCommand
from django.db import transaction
from gestionPedidos.models import Producto


class Command(BaseCommand):
    help = 'Detecta y, opcionalmente, consolida imágenes idénticas en media/productos.'

    def add_arguments(self, parser):
        parser.add_argument('--apply', action='store_true', help='Actualizar referencias y eliminar copias redundantes.')

    def handle(self, *args, **options):
        base = Path(settings.MEDIA_ROOT) / 'productos'
        if not base.is_dir():
            self.stdout.write('No existe media/productos/.')
            return
        grupos = defaultdict(list)
        for archivo in base.iterdir():
            if not archivo.is_file():
                continue
            huella = hashlib.sha256()
            with archivo.open('rb') as fd:
                for bloque in iter(lambda: fd.read(1024 * 1024), b''):
                    huella.update(bloque)
            grupos[huella.hexdigest()].append(archivo)

        encontrados = [g for g in grupos.values() if len(g) > 1]
        if not encontrados:
            self.stdout.write('Sin duplicados idénticos.')
            return

        for grupo in encontrados:
            # Preferir nombres humanos conocidos y fotos referenciadas.
            def prioridad(f):
                ruta = 'productos/' + f.name
                usados = Producto.objects.filter(imagen=ruta).count()
                es_hash = f.stem.lower() == hashlib.sha256(f.read_bytes()).hexdigest()
                return (-usados, es_hash, f.name.lower())
            origen = sorted(grupo, key=prioridad)[0]
            self.stdout.write('Conservar: ' + origen.name)
            for duplicado in grupo:
                if duplicado == origen:
                    continue
                self.stdout.write('  Duplicado: ' + duplicado.name)
                if options['apply']:
                    ruta_origen = 'productos/' + origen.name
                    ruta_duplicada = 'productos/' + duplicado.name
                    with transaction.atomic():
                        Producto.objects.filter(imagen=ruta_duplicada).update(imagen=ruta_origen)
                    if not Producto.objects.filter(imagen=ruta_duplicada).exists():
                        duplicado.unlink()
                        self.stdout.write('  Eliminado de disco: ' + duplicado.name)
        if not options['apply']:
            self.stdout.write('Solo revisión. Respaldar media/ y BD; ejecutar --apply para consolidar.')
