from django.contrib import messages
from django.contrib.auth import login as auth_login
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.shortcuts import redirect, render
from django.urls import reverse_lazy
from django.views.generic import CreateView

from accounts.forms import ProfileModelForm, SignupForm, UserModelForm


class RegisterView(CreateView):
    """Self-service registration. Login / logout / password-change /
    password-reset are django.contrib.auth.views, wired in urls.py."""
    form_class = SignupForm
    template_name = 'accounts/register.html'
    success_url = reverse_lazy('dashboard')

    def form_valid(self, form):
        response = super().form_valid(form)
        auth_login(self.request, self.object)
        messages.success(self.request, 'Welcome to CPDraw.')
        return response


@login_required
@transaction.atomic
def update_profile(request):
    if request.method == 'POST':
        user_form = UserModelForm(request.POST, instance=request.user)
        profile_form = ProfileModelForm(request.POST, instance=request.user.profile)
        if user_form.is_valid() and profile_form.is_valid():
            user_form.save()
            profile_form.save()
            messages.success(request, 'Your profile was updated.')
            return redirect('profile')
        messages.error(request, 'Please correct the errors below.')
    else:
        user_form = UserModelForm(instance=request.user)
        profile_form = ProfileModelForm(instance=request.user.profile)

    return render(request, 'accounts/profile.html', {
        'user_form': user_form,
        'profile_form': profile_form,
    })
