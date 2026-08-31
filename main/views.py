from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import JsonResponse
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.views.generic import CreateView, DeleteView, ListView, UpdateView

from .utils import myprojects
from main.iiif import ingest_source
from main.iiif.exceptions import IngestError
from main.models import Project, ProjectUser, ProjectPlacetype, Source
from main.forms import ProjectCreateModelForm

# NOTE (WO-0.2): the Leaflet-era Draw page, Map CRUD, Feature CRUD, and the
# CSV/LPF export (download_project / get_minmax / maketime) were removed here
# when Map/Feature/Name were dropped from the model. The OpenSeadragon Draw
# page returns in WO-0.3, annotation persistence in WO-0.4, and LPF export in
# Phase 1 (rebuilt against Annotation). Prior code is in git history.


class DashboardView(LoginRequiredMixin, ListView):
  context_object_name = 'project_list'
  template_name = 'main/dashboard.html'

  login_url = '/accounts/login/'
  redirect_field_name = 'redirect_to'

  def get_queryset(self):
    me = self.request.user
    if me.username in ['admin', 'karlg']:
      return Project.objects.all().order_by('label')
    return Project.objects.filter(
      Q(id__in=myprojects(me)) | Q(owner=me)).order_by('label')


class ProjectCreateView(LoginRequiredMixin, CreateView):
  form_class = ProjectCreateModelForm
  template_name = 'main/project_create.html'
  success_message = 'project created'
  success_url = "/home/dashboard/"

  login_url = '/accounts/login/'
  redirect_field_name = 'redirect_to'


class ProjectUpdateView(LoginRequiredMixin, UpdateView):
  login_url = '/accounts/login/'
  redirect_field_name = 'redirect_to'
  success_url = "/home/dashboard/"

  template_name = 'main/project_update.html'
  model = Project
  fields = ['id', 'title', 'label', 'owner', 'uri']

  def get_context_data(self, *args, **kwargs):
    context = super().get_context_data(*args, **kwargs)
    pk = self.kwargs.get("pk")
    context['project_id'] = pk
    context['sources'] = (Source.objects
                          .filter(project_id=pk)
                          .annotate(image_count=Count('images'))
                          .order_by('label', 'id'))
    return context


@login_required
def add_source(request, pk):
  """Ingest a IIIF Manifest or Image service into a project (WO-0.2)."""
  project = get_object_or_404(Project, pk=pk)
  if request.method == 'POST':
    uri = (request.POST.get('uri') or '').strip()
    if not uri:
      messages.error(request, 'Enter a IIIF Manifest or Image-service URI.')
    else:
      try:
        src = ingest_source(uri, project=project, owner=request.user)
      except IngestError as exc:
        messages.error(request, f'Ingest failed: {exc}')
      else:
        n = src.images.count()
        messages.success(
          request,
          f'Added source #{src.pk} ({src.get_ingest_kind_display()}) — '
          f'{n} image{"" if n == 1 else "s"}.')
  return redirect('project-update', pk=pk)


class ProjectDeleteView(DeleteView):
  template_name = 'main/project_delete.html'

  def get_object(self):
    return get_object_or_404(Project, id=self.kwargs.get("id"))

  def get_success_url(self):
    return reverse('main:dashboard')


@login_required
def fetchProjects(request):
  u = request.user
  result = {"projects": [], "maps": []}
  if u.is_superuser:
    projects = Project.objects.all()
  else:
    collab_projects = ProjectUser.objects.filter(user=u).values_list('project', flat=True)
    projects = Project.objects.filter(Q(id__in=collab_projects) | Q(owner=u))

  for p in projects:
    placetypes = [t.as_dict() for t in ProjectPlacetype.objects.filter(project=p)]
    result['projects'].append({
      'id': p.id, 'owner': p.owner_id, 'label': p.label, 'title': p.title,
      'placetypes': placetypes,
    })

  return JsonResponse(result, safe=False)
