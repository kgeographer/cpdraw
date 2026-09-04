from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from django.db import transaction

from accounts.models import Profile


class SignupForm(UserCreationForm):
    """Django's UserCreationForm (username + two passwords, with the password
    validators) plus the fields CPDraw wants: a required e-mail and full name,
    optional affiliation and web page. Populates the signal-created Profile."""

    email = forms.EmailField(required=True)
    name = forms.CharField(max_length=200, required=True, label='Full name')
    affiliation = forms.CharField(max_length=200, required=False)
    web_page = forms.URLField(required=False, label='Web page')

    class Meta(UserCreationForm.Meta):
        model = User
        fields = ('username', 'email')

    @transaction.atomic
    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data['email']
        if commit:
            user.save()  # post_save → create_user_profile makes the Profile row
            profile, _ = Profile.objects.get_or_create(user=user)
            profile.name = self.cleaned_data['name']
            profile.affiliation = self.cleaned_data['affiliation']
            profile.web_page = self.cleaned_data['web_page'] or None
            profile.save()
        return user


class UserModelForm(forms.ModelForm):
    """The editable-on-the-profile-page slice of User — just the e-mail."""

    class Meta:
        model = User
        fields = ('email',)
        widgets = {'email': forms.EmailInput(attrs={'size': 40})}


class ProfileModelForm(forms.ModelForm):
    # Profile.web_page is null=True but (inherited) blank=False, which would
    # make it required on this form. Optional here; model cleanup is a follow-up.
    web_page = forms.URLField(required=False)

    class Meta:
        model = Profile
        fields = ('name', 'affiliation', 'web_page')
        widgets = {
            'name': forms.TextInput(attrs={'size': 40}),
            'affiliation': forms.TextInput(attrs={'size': 40}),
            'web_page': forms.TextInput(attrs={'size': 40}),
        }
