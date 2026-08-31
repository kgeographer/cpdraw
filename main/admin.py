from django.contrib import admin

from .models import Project, ProjectUser, Source, MapImage, WorkState


class MapImageInline(admin.TabularInline):
    model = MapImage
    extra = 0
    fields = ('seq', 'label', 'image_service_uri', 'width', 'height', 'needs_metadata')
    show_change_link = True


@admin.register(Source)
class SourceAdmin(admin.ModelAdmin):
    list_display = ('__str__', 'project', 'ingest_kind', 'iiif_version', 'fetched_at')
    list_filter = ('project', 'ingest_kind')
    search_fields = ('label', 'title', 'iiif_label', 'ingest_uri')
    inlines = [MapImageInline]


@admin.register(MapImage)
class MapImageAdmin(admin.ModelAdmin):
    list_display = ('__str__', 'source', 'seq', 'width', 'height', 'needs_metadata')
    list_filter = ('needs_metadata', 'source__project')
    search_fields = ('label', 'image_service_uri', 'canvas_uri')


admin.site.register(Project)
admin.site.register(ProjectUser)
admin.site.register(WorkState)
