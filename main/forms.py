# main.forms

from django import forms
from .models import Project


# id, title, label, owner_id, create_date, uri
class ProjectCreateModelForm(forms.ModelForm):

    class Meta:
        model = Project
        fields = ('title', 'label', 'owner', 'uri')

    def __init__(self, *args, **kwargs):
        super(ProjectCreateModelForm, self).__init__(*args, **kwargs)
        for field in self.fields.values():
            field.error_messages = {'required': 'The field {fieldname} is required'.format(
                fieldname=field.label)}

# NOTE (WO-0.2): MapCreateModelForm removed with the Map model. A Source
# create/edit form arrives with the ingest flow.
