# main.forms

from django import forms
from django.contrib.postgres.forms import SimpleArrayField

from .models import Project


class ProjectForm(forms.ModelForm):
    """Create + edit a project. `owner` is set from the request in the view,
    never through the form. The spatial-scope fields (scoping doc §3) are
    optional, comma-separated free text, validated here."""

    scope_ccodes = SimpleArrayField(
        forms.CharField(max_length=2), required=False, label='Country codes',
        help_text='ISO 3166-1 alpha-2, comma-separated — e.g. PL, UA')
    scope_bbox = SimpleArrayField(
        forms.FloatField(), required=False, label='Bounding box',
        help_text='west, south, east, north (decimal degrees); leave blank if unknown')

    class Meta:
        model = Project
        fields = ('title', 'label', 'uri',
                  'scope_ccodes', 'scope_bbox', 'scope_note')

    def clean_scope_ccodes(self):
        out = []
        for code in self.cleaned_data.get('scope_ccodes') or []:
            code = code.strip().upper()
            if len(code) != 2 or not code.isalpha():
                raise forms.ValidationError(f'"{code}" is not a 2-letter country code.')
            out.append(code)
        return out or None

    def clean_scope_bbox(self):
        bbox = self.cleaned_data.get('scope_bbox')
        if not bbox:
            return None
        if len(bbox) != 4:
            raise forms.ValidationError('Give exactly four numbers: west, south, east, north.')
        w, s, e, n = bbox
        if w >= e:
            raise forms.ValidationError('West must be less than east.')
        if s >= n:
            raise forms.ValidationError('South must be less than north.')
        return bbox
