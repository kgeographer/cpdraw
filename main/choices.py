# Project membership roles (WO-0.5 §1.2). Ordered most- to least-privileged:
#   owner     — all permissions on the project; edits metadata/scope, deletes,
#               mints join keys (WO-0.6). Not a superuser.
#   editor    — adds sources and edits their metadata; edits any annotation;
#               manages the placetype vocabulary and per-map subsets.
#   annotator — creates annotations and edits their own.
# `Project.owner` (the FK) is an implicit owner-role membership.
TEAMROLES = [
    ('owner', 'Owner'),
    ('editor', 'Editor'),
    ('annotator', 'Annotator'),
]
