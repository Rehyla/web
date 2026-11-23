import uuid

from django.db import models

class Usuario(models.Model):
    rut             = models.CharField(max_length=12, primary_key=True)
    usuario         = models.TextField(max_length=40)
    nombres         = models.TextField(max_length=40)
    apellidos       = models.TextField(max_length=40)
    rol             = models.TextField(max_length=40)
    password        = models.TextField(max_length=256)  # Hash seguro, nunca texto plano
    complejidad     = models.CharField(max_length=10) # Alta, Media, Baja

class Producto(models.Model):
    nombre          = models.TextField(max_length=40)
    descripcion     = models.TextField(max_length=40)
    precio          = models.IntegerField(null=False)
    imagen          = models.ImageField(upload_to='productos/', null=True, blank=True)
    categoria       = models.TextField(max_length=40)

class Menu(models.Model):
    producto = models.ForeignKey(Producto, on_delete=models.CASCADE)
    dia = models.DateField()



class Pedido(models.Model):
    usuario = models.ForeignKey(Usuario, on_delete=models.CASCADE)
    fecha = models.DateTimeField()
    tipoPago = models.TextField(max_length=100)
    total = models.IntegerField(null=False)
    estado = models.IntegerField(null=False)  # 1: registrado; 0: cancelado
    motivo_cancelacion = models.CharField(max_length=250, blank=True, default="")
    fecha_cancelacion = models.DateTimeField(null=True, blank=True)
    duracion_atencion_segundos = models.PositiveIntegerField(null=True, blank=True)

class DetallePedido(models.Model):
    pedido = models.ForeignKey(Pedido, on_delete=models.CASCADE)
    producto = models.ForeignKey(Producto, on_delete=models.CASCADE)
    cantidad = models.IntegerField(null=False)
    precio = models.IntegerField(null=False)
    


# NUEVO: Estados exclusivamente para la pantalla de cocina.
# No modifica Pedido.estado ni los pedidos/historiales existentes.
class EstadoPedidoCocina(models.Model):
    ESTADOS = [
        ('pendiente', 'Pendiente'),
        ('listo', 'Listo'),
        ('alerta', 'Con problema'),
    ]

    pedido = models.OneToOneField(
        Pedido, on_delete=models.CASCADE, related_name='estado_cocina'
    )
    estado = models.CharField(max_length=10, choices=ESTADOS, default='pendiente')
    tuvo_problema = models.BooleanField(default=False)
    observacion = models.CharField(max_length=200, blank=True, default='')
    actualizado_en = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f'Pedido #{self.pedido_id}: {self.get_estado_display()}'


class EncuestaSatisfaccion(models.Model):
    class Calificacion(models.IntegerChoices):
        MUY_INSATISFECHO = 1, 'Muy insatisfecho'
        INSATISFECHO = 2, 'Insatisfecho'
        NEUTRO = 3, 'Neutral'
        SATISFECHO = 4, 'Satisfecho'
        MUY_SATISFECHO = 5, 'Muy satisfecho'

    codigo = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    pedido = models.OneToOneField(Pedido, on_delete=models.CASCADE, related_name='encuesta')
    nombre_cliente = models.CharField(max_length=80, blank=True, default='')
    calificacion = models.PositiveSmallIntegerField(
        choices=Calificacion.choices, null=True, blank=True
    )

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=(
                    models.Q(calificacion__isnull=True)
                    | models.Q(calificacion__range=(1, 5))
                ),
                name='encuesta_calificacion_valida',
            ),
        ]
