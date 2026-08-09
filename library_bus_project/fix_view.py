import sys
import re

with open('transactions/views.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Make sure FormView is imported
if 'FormView' not in content:
    content = content.replace('from django.views.generic import ListView, DetailView, CreateView', 'from django.views.generic import ListView, DetailView, CreateView, FormView')
    content = content.replace('from django.views.generic import CreateView, ListView, DetailView', 'from django.views.generic import CreateView, ListView, DetailView, FormView')
    # fallback
    if 'FormView' not in content:
        content = 'from django.views.generic import FormView\n' + content

# Change CreateReservationView
# It currently has: class CreateReservationView(LoginRequiredMixin, CreateView):
# We will change CreateView to FormView and remove `model = BookReservation`
content = content.replace('class CreateReservationView(LoginRequiredMixin, CreateView):', 'class CreateReservationView(LoginRequiredMixin, FormView):')
content = content.replace('    model = BookReservation\n', '')

with open('transactions/views.py', 'w', encoding='utf-8') as f:
    f.write(content)
