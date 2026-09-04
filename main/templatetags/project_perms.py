"""Template filters for role-aware UI gating (WO-0.5 §1.2).

Usage:  {% load project_perms %}
        {% if project|can_edit_project:user %} … {% endif %}
"""
from django import template

register = template.Library()


@register.filter
def project_role(project, user):
    return project.role_of(user)


@register.filter
def can_edit_project(project, user):
    return project.can_edit_metadata(user)


@register.filter
def can_add_sources(project, user):
    return project.can_add_sources(user)


@register.filter
def can_manage_vocab(project, user):
    return project.can_manage_vocabulary(user)
