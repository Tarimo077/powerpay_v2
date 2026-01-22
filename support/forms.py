from django import forms
from .models import Ticket

class TicketForm(forms.ModelForm):
    class Meta:
        model = Ticket
        fields = ['subject', 'description', 'priority']
        widgets = {
            'subject': forms.Select(attrs={'class': 'border rounded-lg px-3 py-2 w-full'}),
            'description': forms.Textarea(attrs={'class': 'border rounded-lg px-3 py-2 w-full', 'rows': 5}),
            'priority': forms.Select(attrs={'class': 'border rounded-lg px-3 py-2 w-full'}),
        }
