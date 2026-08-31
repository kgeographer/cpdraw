from django.conf import settings
from django.contrib.auth.models import User
from django.contrib.postgres.fields import ArrayField
from django.db import models
from django.db.models import JSONField
from django.shortcuts import get_object_or_404

from main.choices import TEAMROLES


# ---------------------------------------------------------------------------
# Carried forward from the predecessor (see CLAUDE.md): users, project
# membership, and the AAT placetype-vocabulary scoping. Unchanged.
# ---------------------------------------------------------------------------

class Project(models.Model):
  owner = models.ForeignKey(settings.AUTH_USER_MODEL,
                              related_name='projects', on_delete=models.CASCADE)

  title = models.CharField(max_length=255)
  label = models.CharField(max_length=20)
  uri = models.URLField(blank=True, null=True)
  create_date = models.DateTimeField(null=True, auto_now_add=True)

  @property
  def collab(self):
    projusers=ProjectUser.objects.filter(project_id = self.id)
    collabs=[]
    for pu in projusers:
      u = get_object_or_404(User, id=pu.user_id)
      collabs.append(u)
    return collabs

  def __str__(self):
    return self.label

  class Meta:
    managed = True
    db_table = 'projects'


class ProjectUser(models.Model):
  project = models.ForeignKey(Project, related_name='projects',
                                default=-1, on_delete=models.CASCADE)
  user = models.ForeignKey(User, related_name='users',
                             default=-1, on_delete=models.CASCADE)
  role = models.CharField(max_length=20, null=False, choices=TEAMROLES)

  class Meta:
    managed = True
    db_table = 'project_user'


class Placetype(models.Model):
  aat_id = models.IntegerField(unique=True)
  parent_id = models.IntegerField(null=True,blank=True)
  term = models.CharField(max_length=100)
  term_full = models.CharField(max_length=100)
  note = models.TextField(max_length=3000)
  fclass = models.CharField(max_length=1,null=True,blank=True)

  def __str__(self):
    return str(self.aat_id) +':'+self.term
  def as_dict(self):
    return {
      "aat_id": self.aat_id,
      "term": self.term,
      "fclass": self.fclass
    }
  class Meta:
    managed = True
    db_table = 'placetypes'


# placetypes designated per project
class ProjectPlacetype(models.Model):
  """A project's own place-type vocabulary. `source_label` is the user's term
  (any language); `aattype` is an optional mapping into the master AAT table.
  Mirrors WHG LP-TSV `types[]` / `aat_types[]`."""
  project = models.ForeignKey(Project, related_name='placetypes', on_delete=models.CASCADE)
  aattype = models.ForeignKey(Placetype, to_field='aat_id', null=True, blank=True,
                              on_delete=models.SET_NULL)
  source_label = models.CharField(max_length=100)

  @property
  def aat_term(self):
    if self.aattype_id is None:
      return ''
    pt = Placetype.objects.filter(aat_id=self.aattype_id).first()
    return pt.term if pt else ''

  def __str__(self):
    return self.source_label

  def as_dict(self):
    return {
      "id": self.pk,
      "sourceLabel": self.source_label,
      "identifier": f"aat:{self.aattype_id}" if self.aattype_id else None,
      "label": self.aat_term or None,
    }

  class Meta:
    managed = True
    db_table = 'project_placetype'
    ordering = ['project', 'source_label']


# ---------------------------------------------------------------------------
# CPDraw domain model (WO-0.2). Replaces the predecessor's Map / Feature.
#
#   Source     one IIIF Manifest, or a bare Image service
#     MapImage   one Canvas / Image within the Source; annotations attach here
#       WorkState  assignment / status / lock (stub for Phase 0)
#
# Annotation and Georeference arrive in later work orders. See
# docs/WO_0.2.md and the scoping document §3.
# ---------------------------------------------------------------------------

class Source(models.Model):
  """One IIIF resource — a Presentation Manifest, or a bare Image service."""
  project = models.ForeignKey('main.Project', db_column='project',
                              related_name='sources', on_delete=models.CASCADE)
  owner = models.ForeignKey(settings.AUTH_USER_MODEL,
                            related_name='sources', on_delete=models.PROTECT)
  created = models.DateTimeField(auto_now_add=True)
  modified = models.DateTimeField(auto_now=True)

  # -- ingest provenance ----------------------------------------------------
  class IngestKind(models.TextChoices):
    MANIFEST = 'manifest', 'IIIF Presentation Manifest'
    IMAGE_SERVICE = 'image_service', 'IIIF Image service / info.json'

  ingest_uri = models.URLField(max_length=2048)
  ingest_kind = models.CharField(max_length=16, choices=IngestKind.choices)
  iiif_version = models.CharField(max_length=8, blank=True)          # '2' | '3' | ''
  fetched_at = models.DateTimeField(null=True, blank=True)
  raw_document = models.TextField(blank=True)                        # exactly as fetched
  normalization_log = JSONField(default=list, blank=True)           # [{rule, note}, ...]

  # -- manifest-derived (populated on fetch; CPDraw never overwrites) ------
  iiif_label = models.CharField(max_length=1000, blank=True)
  iiif_metadata = JSONField(default=list, blank=True)               # IIIF metadata[] verbatim
  iiif_rights = models.CharField(max_length=500, blank=True)
  iiif_summary = models.TextField(blank=True)                       # v3 summary / v2 description
  iiif_required_statement = JSONField(null=True, blank=True)        # {label, value}
  nav_date = models.CharField(max_length=64, blank=True)            # raw navDate string

  # -- CPDraw-authored (sit alongside; may be blank) ---------------------
  label = models.SlugField(max_length=32, blank=True)              # short handle, unique per project
  title = models.CharField(max_length=500, blank=True)
  citation = models.TextField(blank=True)
  citation_uri = models.URLField(max_length=1024, blank=True)
  year_pub = models.IntegerField(null=True, blank=True)
  when = JSONField(null=True, blank=True)                           # JSONB timespan (§3)

  # -- spatial scope override (§3); inherits Project when unset ---------
  scope_ccodes = ArrayField(models.CharField(max_length=2), null=True, blank=True)
  scope_bbox = ArrayField(models.FloatField(), size=4, null=True, blank=True)  # [w, s, e, n]
  scope_note = models.CharField(max_length=255, blank=True)

  def __str__(self):
    return self.label or self.title or self.iiif_label or f'source {self.pk}'

  class Meta:
    managed = True
    db_table = 'sources'
    ordering = ['project', 'label', 'id']
    constraints = [
      models.UniqueConstraint(fields=['project', 'label'],
                              condition=~models.Q(label=''),
                              name='uniq_source_label_per_project'),
    ]


class MapImage(models.Model):
  """One IIIF Canvas / Image within a Source. Annotations attach here (WO-0.4)."""
  source = models.ForeignKey('main.Source', db_column='source',
                             related_name='images', on_delete=models.CASCADE)
  seq = models.PositiveIntegerField(default=0)                      # canvas order within the source

  canvas_uri = models.URLField(max_length=2048, blank=True)        # '' when degraded from a bare image service
  image_service_uri = models.URLField(max_length=2048)
  info_json = JSONField(null=True, blank=True)                     # the image info.json, retained
  width = models.PositiveIntegerField(null=True, blank=True)
  height = models.PositiveIntegerField(null=True, blank=True)

  label = models.CharField(max_length=1000, blank=True)            # per-image override
  when = JSONField(null=True, blank=True)                          # per-image override

  # Advisory notes from main.iiif.quality.assess() — resolution / tiling
  # fitness for tracing. [{level, code, message}, ...]. Never blocks ingest.
  quality_notes = JSONField(default=list, blank=True)

  needs_metadata = models.BooleanField(default=False)              # created via the degradation path
  created = models.DateTimeField(auto_now_add=True)
  modified = models.DateTimeField(auto_now=True)

  def __str__(self):
    return self.label or f'{self.source} #{self.seq}'

  @property
  def has_quality_warning(self):
    return any(n.get('level') == 'warning' for n in self.quality_notes)

  class Meta:
    managed = True
    db_table = 'map_images'
    ordering = ['source', 'seq']
    constraints = [
      models.UniqueConstraint(fields=['source', 'seq'],
                              name='uniq_mapimage_seq_per_source'),
    ]


class WorkState(models.Model):
  """Per-image assignment / status / lock. Minimal for Phase 0 (single-user)."""
  image = models.OneToOneField('main.MapImage', db_column='image',
                               related_name='workstate', on_delete=models.CASCADE)

  class Status(models.TextChoices):
    UNSTARTED = 'unstarted', 'Not started'
    IN_PROGRESS = 'in_progress', 'In progress'
    COMPLETE = 'complete', 'Complete'

  status = models.CharField(max_length=16, choices=Status.choices, default=Status.UNSTARTED)
  assignee = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True,
                               related_name='assigned_images', on_delete=models.SET_NULL)
  locked_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True,
                                related_name='locked_images', on_delete=models.SET_NULL)
  locked_at = models.DateTimeField(null=True, blank=True)
  modified = models.DateTimeField(auto_now=True)

  def __str__(self):
    return f'{self.image} · {self.status}'

  class Meta:
    managed = True
    db_table = 'work_states'


class Annotation(models.Model):
  """A feature drawn on a MapImage, in image (pixel) coordinates (WO-0.4).

  The row is CPDraw's source of truth: `w3c` holds the annotation as
  Annotorious emits it (the pixel geometry lives in its SvgSelector); the
  named columns are what CPDraw and later LPF work from. See docs/WO_0.4.md.
  """
  image = models.ForeignKey('main.MapImage', db_column='image',
                            related_name='annotations', on_delete=models.CASCADE)

  class GeometryType(models.TextChoices):
    POLYGON = 'polygon', 'Polygon'
    POLYLINE = 'polyline', 'Polyline'
    POINT = 'point', 'Point'          # deferred to Phase 1

  class FeatureRole(models.TextChoices):
    REGION = 'region', 'Region'
    LABEL = 'label', 'Label'          # letterspacing extent gesture (§4)
    BOUNDARY = 'boundary', 'Boundary'  # a traced drawn border
    SITE = 'site', 'Site'             # deferred to Phase 1

  class Certainty(models.TextChoices):
    CERTAIN = 'certain', 'Certain'
    LIKELY = 'likely', 'Likely'
    UNCERTAIN = 'uncertain', 'Uncertain'

  geometry_type = models.CharField(max_length=12, choices=GeometryType.choices)
  feature_role = models.CharField(max_length=12, choices=FeatureRole.choices)

  name = models.CharField(max_length=255, blank=True)             # verbatim transcription
  name_normalized = models.CharField(max_length=255, blank=True)  # optional editorial
  placetype = models.ForeignKey('main.ProjectPlacetype', null=True, blank=True,
                                related_name='annotations', on_delete=models.SET_NULL)
  certainty = models.CharField(max_length=12, choices=Certainty.choices, blank=True)
  when = JSONField(null=True, blank=True)                         # per-feature temporal override

  w3c = JSONField(default=dict, blank=True)                       # annotation as Annotorious emits it
  bbox = ArrayField(models.FloatField(), size=4, null=True, blank=True)  # [x0, y0, x1, y1] in px

  created_by = models.ForeignKey(settings.AUTH_USER_MODEL,
                                 related_name='annotations', on_delete=models.PROTECT)
  modified_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True,
                                  related_name='annotations_modified', on_delete=models.SET_NULL)
  created = models.DateTimeField(auto_now_add=True)
  modified = models.DateTimeField(auto_now=True)

  def __str__(self):
    return self.name or f'{self.get_feature_role_display()} {self.pk}'

  class Meta:
    managed = True
    db_table = 'annotations'
    ordering = ['image', 'created']
