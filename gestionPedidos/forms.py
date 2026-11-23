from django import forms

from .models import EncuestaSatisfaccion


class EncuestaSatisfaccionForm(forms.Form):
    nombre_cliente = forms.CharField(
        label='Nombre del cliente',
        max_length=80,
        required=False,
        widget=forms.TextInput(attrs={'autocomplete': 'name'}),
        error_messages={'max_length': 'Escribe un nombre de hasta 80 caracteres.'},
    )
    calificacion = forms.TypedChoiceField(
        choices=EncuestaSatisfaccion.Calificacion.choices,
        coerce=int,
        widget=forms.RadioSelect,
        error_messages={
            'required': 'Selecciona una opción para enviar tu respuesta.',
            'invalid_choice': 'Selecciona una de las cinco opciones disponibles.',
        },
    )
