from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import JsonResponse
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.generic import CreateView, DeleteView, DetailView, ListView, UpdateView

from urllib.parse import urlencode

from .utils import myprojects
from main.iiif import ingest_source, preflight
from main.iiif.exceptions import IngestError
from main.models import (MapImage, Placetype, Project, ProjectPlacetype,
                         ProjectUser, Source)
from main.forms import ProjectCreateModelForm

# Starter place-type vocabulary seeded into every new project (WO-0.4). Bregel's
# five; the AAT mapping is attached only if load_aat_feature_types has been run.
STARTER_PLACETYPES = [
  ('historical region', 300387178),
  ('inhabited place', 300008347),
  ('archaeological site', 300000810),
  ('dynasty', 300386176),
  ('cultural group', 300387171),
]

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

  def _visible_projects(self):
    me = self.request.user
    if me.is_superuser or me.username in ['admin', 'karlg']:
      return Project.objects.all()
    return Project.objects.filter(Q(id__in=myprojects(me)) | Q(owner=me))

  def get_queryset(self):
    return self._visible_projects().order_by('label')

  def get_context_data(self, *args, **kwargs):
    context = super().get_context_data(*args, **kwargs)
    context['map_images'] = (
      MapImage.objects
      .filter(source__project__in=self._visible_projects())
      .select_related('source', 'source__project', 'workstate')
      .order_by('source__project__label', 'source__label', 'source_id', 'seq')
    )
    return context


class DrawView(LoginRequiredMixin, DetailView):
  """WO-0.3: render one MapImage in the OpenSeadragon viewer."""
  model = MapImage
  pk_url_kwarg = 'image_id'
  template_name = 'main/draw.html'
  context_object_name = 'image'
  login_url = '/accounts/login/'

  def get_queryset(self):
    return MapImage.objects.select_related(
      'source', 'source__project', 'workstate')

  def get_context_data(self, **kwargs):
    ctx = super().get_context_data(**kwargs)
    base = self.object.image_service_uri.rstrip('/')
    ctx['iiif_info_url'] = f'{base}/info.json'
    return ctx


class ProjectCreateView(LoginRequiredMixin, CreateView):
  form_class = ProjectCreateModelForm
  template_name = 'main/project_create.html'
  success_message = 'project created'
  success_url = "/home/dashboard/"

  login_url = '/accounts/login/'
  redirect_field_name = 'redirect_to'

  def form_valid(self, form):
    response = super().form_valid(form)
    aat = {p.aat_id: p for p in Placetype.objects.filter(
      aat_id__in=[a for _, a in STARTER_PLACETYPES])}
    ProjectPlacetype.objects.bulk_create([
      ProjectPlacetype(project=self.object, source_label=label,
                       aattype=aat.get(aat_id))
      for label, aat_id in STARTER_PLACETYPES
    ])
    return response


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
                          .prefetch_related('images__workstate')
                          .order_by('label', 'id'))
    return context


@login_required
def add_source(request, pk):
  """Ingest a IIIF Manifest or Image service into a project.

  Preflight first: if the quality check turns up warnings and the user didn't
  tick 'add anyway', bounce back with the specifics and create nothing.
  """
  project = get_object_or_404(Project, pk=pk)
  back = redirect('project-update', pk=pk)

  if request.method != 'POST':
    return back

  uri = (request.POST.get('uri') or '').strip()
  add_anyway = bool(request.POST.get('add_anyway'))
  if not uri:
    messages.error(request, 'Enter a IIIF Manifest or Image-service URI.')
    return back

  if not add_anyway:
    try:
      pf = preflight(uri)
    except IngestError as exc:
      messages.error(request, f'Ingest failed: {exc}')
      return back
    if pf.has_warnings:
      messages.warning(request, (
        'That source looks marginal for tracing: '
        + '; '.join(pf.warning_lines)
        + ". Tick “add anyway” and resubmit to keep it."))
      url = reverse('project-update', args=[pk]) + '?' + urlencode({'add_uri': uri})
      return redirect(url)

  try:
    src = ingest_source(uri, project=project, owner=request.user)
  except IngestError as exc:
    messages.error(request, f'Ingest failed: {exc}')
    return back

  n = src.images.count()
  messages.success(
    request,
    f'Added source #{src.pk} ({src.get_ingest_kind_display()}) — '
    f'{n} image{"" if n == 1 else "s"}.')
  return back


@login_required
def project_placetypes(request, pk):
  """Manage a project's place-type vocabulary (WO-0.4)."""
  project = get_object_or_404(Project, pk=pk)
  if request.method == 'POST':
    if request.POST.get('delete'):
      ProjectPlacetype.objects.filter(pk=request.POST['delete'], project=project).delete()
      messages.success(request, 'Type removed.')
    else:
      label = (request.POST.get('source_label') or '').strip()
      aat_id = (request.POST.get('aattype') or '').strip()
      if not label:
        messages.error(request, 'Enter a term.')
      else:
        aat = Placetype.objects.filter(aat_id=aat_id).first() if aat_id.isdigit() else None
        ProjectPlacetype.objects.create(project=project, source_label=label, aattype=aat)
        messages.success(request, f'Added “{label}”.')
    return redirect('project-types', pk=pk)

  return render(request, 'main/project_placetypes.html', {
    'project': project,
    'placetypes': project.placetypes.select_related('aattype').all(),
  })


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
