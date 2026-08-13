from django import forms
from .models import Ticket

INPUT_CLASS = (
    "w-full rounded-xl border border-base-300 bg-base-100 px-4 py-2.5 text-sm "
    "focus:outline-none focus:border-success focus:ring-2 focus:ring-success/20 transition"
)


class TicketForm(forms.ModelForm):
    class Meta:
        model = Ticket
        fields = ['subject', 'description', 'priority']
        labels = {
            'subject': 'What is this about?',
            'description': 'Describe the issue',
            'priority': 'Priority',
        }
        help_texts = {
            'description': 'Include device IDs, error messages or steps to reproduce where possible.',
            'priority': 'High priority is for issues blocking operations right now.',
        }
        widgets = {
            'subject': forms.Select(attrs={'class': INPUT_CLASS}),
            'description': forms.Textarea(attrs={
                'class': INPUT_CLASS,
                'rows': 6,
                'placeholder': 'Tell us what happened...',
            }),
            'priority': forms.Select(attrs={'class': INPUT_CLASS}),
        }
