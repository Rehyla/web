"""Migra contraseñas antiguas en texto plano a hashes Django. NO revela claves."""
from django.core.management.base import BaseCommand
from django.contrib.auth.hashers import identify_hasher, make_password
from django.db import transaction
from gestionPedidos.models import Usuario


class Command(BaseCommand):
    help = 'Detecta contraseñas antiguas y, con --apply, las convierte a hashes Django.'

    def add_arguments(self, parser):
        parser.add_argument('--apply', action='store_true', help='Aplicar los cambios (sin esto, solo informa).')

    def handle(self, *args, **options):
        pendientes = []
        protegidas = 0
        vacias = 0
        for usuario in Usuario.objects.all().iterator():
            clave = usuario.password or ''
            if not clave or clave.startswith('!'):
                vacias += 1
                continue
            try:
                identify_hasher(clave)
            except ValueError:
                # No se imprime la contraseña ni se exporta en archivos.
                pendientes.append((usuario.pk, clave))
            else:
                protegidas += 1

        self.stdout.write(f'Ya protegidas: {protegidas}. Pendientes: {len(pendientes)}. Sin clave: {vacias}.')
        if not options['apply']:
            self.stdout.write('Modo revisión. Respaldar la BD y ejecutar con --apply para convertir.')
            return

        with transaction.atomic():
            for rut, clave in pendientes:
                Usuario.objects.filter(pk=rut).update(password=make_password(clave))
        self.stdout.write(self.style.SUCCESS(f'Convertidas a hash: {len(pendientes)}.'))
