# WO-0.5 — auth, project, and map-list views wired through

**Status:** working spec, for review. Decomposes scoping-doc §10 Phase 0 "WO-0.5 —
Existing auth, project, and map-list views wired through". § refs are to
`docs/CPDraw — scoping document.md`.

**Scope:** rebuild the hand-rolled `accounts/` register/login/logout to Django
conventions (`UserCreationForm`, `LoginView`, `LogoutView`); stub the
password-reset plumbing (console email in dev); add optional **spatial scope**
fields to `Project` (the WO_0.2.md §1a carry-over — placetype half landed in
WO-0.4); introduce the project **role model** (`owner | editor | annotator`) with
membership-aware visibility and permission helpers; lock down the project and
source views by role; add the **`MapImagePlacetype`** model (per-map narrowing of
the project vocabulary — the predecessor's deferred `MapPlacetype` tier) so it
rides this migration wave; make the `index → dashboard → project → source →
image → draw` path navigable end to end with back-links; tests.

**Not in scope — deferred to WO-0.6** (committed, not "maybe" — see §1.1):
join keys / invite flow, object-level DRF permission classes on the annotation
and vocabulary endpoints, front-end library modernization (Bootstrap 4 → 5,
jQuery/jQuery-UI removal, CDN pinning), a read-only Source detail page.

---

## 1. Decisions (settled in discussion)

### 1.1 The split

WO-0.5 is steps 1–4 + 7 of the seven-step decomposition; **join keys and
object-level API permissions become WO-0.6.** WO-0.6 is on the roadmap, not
speculative. So the role enum and the permission helpers below are built
role-aware *now* — WO-0.6 adds the invite model and the DRF permission classes
without reworking them.

### 1.2 Roles and permissions

`ProjectUser.role` becomes `owner | editor | annotator` (drop `creator`).

| capability | annotator | editor | owner | superuser |
|---|:-:|:-:|:-:|:-:|
| log in; join a project (via key — WO-0.6) | ✓ | ✓ | ✓ | — |
| create annotations; edit **own** | ✓ | ✓ | ✓ | ✓ |
| edit **any** annotation in the project | | ✓ | ✓ | ✓ |
| add sources; edit source metadata | | ✓ | ✓ | ✓ |
| edit the project placetype vocabulary; set a map's placetype subset | | ✓ | ✓ | ✓ |
| edit project metadata / scope; delete project; mint join keys (WO-0.6) | | | ✓ | ✓ |
| see every project | | | | ✓ |

- **`Project.owner`** (the existing FK) is the founding owner — an *implicit*
  `owner`-role membership. Co-owners are possible as `ProjectUser` rows with
  `role='owner'`. Permission checks read the effective role (FK owner ∪
  membership rows).
- **Superuser = `user.is_superuser` only.** `admin` and `karlg` get the flag set
  in the dev DB (one-off `manage.py shell`, documented in the session log — not
  code). The hardcoded `username in ['admin', 'karlg']` check in `DashboardView`
  goes away.
- **Owners are not superusers** — an owner has every permission *on their
  project*, nothing across projects.
- Enforcement in WO-0.5 is at the **Django view** layer (project + source
  views). The DRF endpoints (`/api/annotations/`, `/api/project-placetypes/`)
  keep `IsAuthenticated` for now; their object-level rules are WO-0.6.

### 1.3 Spatial scope on `Project`

Mirror the three fields `Source` already carries (they were added in WO-0.2 as a
per-source *override* with, until now, no parent to inherit from):

- `scope_ccodes` — `ArrayField(CharField(max_length=2))`, ISO 3166-1 alpha-2
- `scope_bbox` — `ArrayField(FloatField, size=4)`, `[w, s, e, n]`
- `scope_note` — `CharField(max_length=255)`, a named study area or free text

**All `null=True, blank=True`.** Scope is *stated, not derived* (§3) and is not
*used* until Phase 1 gazetteer lookup (§7a) — so capture is plain form fields
(comma-separated codes; four numbers; a note), **no map-draw picker**. The
picker arrives in Phase 1 when scope is first exercised. `Source`'s override
semantics ("inherit `Project` when unset") now have something to inherit.

### 1.4 Map-level placetype scoping — the model now, behavior later

The project defines the **full** placetype vocabulary (`ProjectPlacetype`,
unchanged). A `MapImage` may **narrow** which of those types the annotation
picker offers — the owner/editors decide what a project is after, but a given
sheet may not carry all of it. This is the predecessor's third scoping tier
(`Placetype` → `ProjectPlacetype` → `MapPlacetype`), deferred out of WO-0.4.

New join model, **`MapImagePlacetype`** (§2), with **"no rows = inherit"**
semantics:

- A `MapImage` with **zero** rows → the full `project.placetypes` set is offered.
  This is the default; uncurated maps write nothing.
- A `MapImage` with **≥ 1** row → only those `ProjectPlacetype`s are offered.
- `on_delete=CASCADE` on the `ProjectPlacetype` FK → deleting a project type
  removes it from every map's subset automatically; no dangling ids, no cleanup
  signal, no defensive read-time filtering.
- An existing `Annotation` whose `placetype` was later narrowed out still
  **displays**; it is simply not offered for new picks.
- Chosen over a `MapImage.placetype_ids = ArrayField` precisely for that
  self-cleaning delete — `ProjectPlacetype` deletion is a live button in
  `project_placetypes`.
- Adding a `ProjectPlacetype` later needs **no backfill**: uncurated maps pick it
  up for free (they inherit "all").

**WO-0.5 ships the model + migration only.** The read-path filter (picker shows
`image.placetypes` else the project set) and the editor UI to toggle a map's
subset land with the next annotation-frontend WO — the table already exists then,
so no second migration. Behavior is byte-identical to today until a map is
curated. Setting a map's subset is an **editor+** action (§1.2).

### 1.5 `Profile.user_type` is dropped

Used nowhere but its own form field and template. Remove the column (`accounts`
migration) and `USERTYPES` from `main/choices.py`. Registration collects
**email** (required), **name** (required), **affiliation** and **web_page**
(optional).

### 1.6 Auth uses Django's class-based views

`django.contrib.auth.views.LoginView` / `LogoutView` / `PasswordChangeView` /
`PasswordChangeDoneView` / `PasswordResetView` / `PasswordResetDoneView` /
`PasswordResetConfirmView` / `PasswordResetCompleteView`, wired in
`accounts/urls.py`. Registration is a small `RegisterView(CreateView)` +
`SignupForm(UserCreationForm)` (the one piece Django doesn't ship). Templates
move to `templates/registration/` (Django's default lookup path) with
`accounts/` keeping `register.html` and `profile.html`.

### 1.7 Password reset is plumbed, not finished

Real URL / view / template wiring; `EMAIL_BACKEND = console` in dev so a reset
prints to the `runserver` console; `DEFAULT_FROM_EMAIL` set. SMTP is a
`local_settings.py` / deploy concern — noted, not done here.

### 1.8 Cleanup carried in this WO

- Delete the `add_user_to_public_group` signal (`Group.objects.get(pk=5)` — WHG
  cruft; CPDraw has no groups) and the `Group` imports.
- Delete `accounts/permissions.py` (`IsOwner` / `IsOwnerOrReadOnly` — dead,
  imported nowhere; WO-0.6 writes project-role-aware classes fresh).
- Remove the `print()` debugging in `accounts/views.py`.
- Guard `save_user_profile` (`accounts/models.py`) — it currently calls
  `instance.profile.save()` on *every* `User` save and raises for a User with no
  Profile yet (e.g. `createsuperuser`). `get_or_create` / `hasattr` guard.
- Fix the broken `success_url = "/home/dashboard/"` (that path 404s) on
  `ProjectCreateView` / `ProjectUpdateView`, and `ProjectDeleteView`'s
  `reverse('main:dashboard')` (no such namespaced name).

---

## 2. Model

### `Project` — add

| field | type | notes |
|---|---|---|
| `scope_ccodes` | `ArrayField(CharField(2))`, null, blank | ISO 3166-1 alpha-2 |
| `scope_bbox` | `ArrayField(FloatField, size=4)`, null, blank | `[w, s, e, n]` |
| `scope_note` | `CharField(255)`, blank | named study area / free text |

Plus a manager and permission helpers (no new columns):

- `Project.objects.visible_to(user)` — `is_superuser` → all; else
  `filter(Q(owner=user) | Q(projectuser__user=user)).distinct()`. Replaces
  `DashboardView._visible_projects`, the duplicate in `fetchProjects`, and
  `main/utils.myprojects`.
- `Project.role_of(user)` → `'owner' | 'editor' | 'annotator' | None` (FK owner and
  superuser resolve to `'owner'`).
- `Project.can_edit_metadata(user)` → role is `owner` (or superuser).
- `Project.can_add_sources(user)` → role in `{owner, editor}`.
- `Project.can_manage_vocabulary(user)` → role in `{owner, editor}` — covers
  editing `ProjectPlacetype`s and setting a map's `MapImagePlacetype` subset.
- `Project.can_edit_annotation(user, annotation)` → `annotation.created_by ==
  user` or role in `{owner, editor}`. *(Defined now; first consumed by WO-0.6's
  API permission class — WO-0.5 has no annotation-edit view.)*

### `ProjectUser` — change

- `role` choices → `owner | editor | annotator` (`main/choices.TEAMROLES`).
- Add `unique_together = (('project', 'user'),)` and
  `created = DateTimeField(auto_now_add=True, null=True)`.
- Leave the odd `default=-1` on the `project` / `user` FKs alone — separate
  cleanup, out of scope.
- **Data migration:** any existing `role='creator'` → `'owner'` (dev DB has none;
  write it anyway).

### `MapImagePlacetype` — new (join model, §1.4)

Per-map narrowing of the project vocabulary. "No rows = inherit the full
`project.placetypes` set."

| field | type | notes |
|---|---|---|
| `image` | FK → `MapImage` (CASCADE), `related_name='placetypes'` | |
| `placetype` | FK → `ProjectPlacetype` (CASCADE), `related_name='image_scopes'` | cascade = self-cleaning on vocab delete |

```python
class Meta:
    unique_together = (('image', 'placetype'),)
    db_table = 'map_image_placetype'
```

Read helper (used from the next annotation-frontend WO, not WO-0.5):
`MapImage.available_placetypes` → `self.placetypes` if any, else
`self.source.project.placetypes.all()`.

### `Profile` — change

- Drop `user_type`. Remove `USERTYPES` from `main/choices.py`.

### Migrations

- `main/` — `Project` scope fields; `ProjectUser` role choices + `unique_together`
  + `created`; the `creator → owner` data migration; **`MapImagePlacetype`**. One
  migration for the lot.
- `accounts/` — drop `Profile.user_type`.

Two migrations total for WO-0.5.

---

## 3. Backend

### `accounts/`

- **`forms.py`**
  - `SignupForm(UserCreationForm)` — adds `email` (`EmailField`, required),
    `name` (required), `affiliation`, `web_page` (`URLField`, optional).
    `Meta.model = User`, `fields = ('username', 'email')`; `save()` creates the
    User, sets `email`, and populates the (signal-created) `Profile` in one
    `transaction.atomic()`.
  - `ProfileForm` — trim to `name`, `affiliation`, `web_page`.
  - `UserModelForm` — keep for the email/username row on the profile page;
    `username` rendered read-only.
- **`views.py`**
  - `RegisterView(CreateView)` — `form_class = SignupForm`,
    `template_name = 'accounts/register.html'`; `form_valid` logs the new user in
    and redirects to `dashboard`.
  - Delete the `login` / `logout` functions (→ `auth_views` in `urls.py`).
  - `update_profile` — keep; drop the `print()`s and the groups block; plain
    render; add a "change password" link in the template.
- **`urls.py`**

  ```python
  from django.contrib.auth import views as auth_views

  path('register/', RegisterView.as_view(), name='register'),
  path('login/',  auth_views.LoginView.as_view(), name='login'),
  path('logout/', auth_views.LogoutView.as_view(), name='logout'),
  path('password_change/',      auth_views.PasswordChangeView.as_view(),      name='password_change'),
  path('password_change/done/', auth_views.PasswordChangeDoneView.as_view(),  name='password_change_done'),
  path('password_reset/',       auth_views.PasswordResetView.as_view(),       name='password_reset'),
  path('password_reset/done/',  auth_views.PasswordResetDoneView.as_view(),   name='password_reset_done'),
  path('reset/<uidb64>/<token>/', auth_views.PasswordResetConfirmView.as_view(), name='password_reset_confirm'),
  path('reset/done/',           auth_views.PasswordResetCompleteView.as_view(), name='password_reset_complete'),
  path('profile/', views.update_profile, name='profile'),
  ```
- **`models.py`** — drop `Profile.user_type`; delete `add_user_to_public_group`
  and the `Group` imports; keep `create_user_profile`; guard `save_user_profile`.
- **`permissions.py`** — delete.

### `main/`

- **`forms.py`** — `ProjectForm(ModelForm)`: `fields = ('title', 'label', 'uri',
  'scope_ccodes', 'scope_bbox', 'scope_note')` — **no `owner`**. `scope_ccodes` /
  `scope_bbox` via `django.contrib.postgres.forms.SimpleArrayField`
  (comma-separated) with `clean_*`: upper-case + 2-letter check for ccodes;
  exactly four floats and `w < e`, `s < n` for bbox. Replaces
  `ProjectCreateModelForm`.
- **`views.py`**
  - `ProjectCreateView` — `form_class = ProjectForm`; `form_valid` sets
    `form.instance.owner = self.request.user` before `super()`, then
    `ProjectUser.objects.create(project=self.object, user=self.request.user,
    role='owner')`, then the existing starter-vocab seed. `success_url =
    reverse_lazy('dashboard')`.
  - `ProjectUpdateView` — `form_class = ProjectForm`; `get_queryset()` →
    `Project.objects.filter(pk=self.kwargs['pk'])` intersected with
    `can_edit_metadata` (404 otherwise). Fix `success_url`.
  - `ProjectDeleteView` — add `LoginRequiredMixin`; `get_object()` raises 404
    unless `can_edit_metadata`. Fix `get_success_url` → `reverse('dashboard')`.
  - `add_source` — `if not project.can_add_sources(request.user):` →
    `HttpResponseForbidden`. (Keeps the existing preflight flow otherwise.)
  - `project_placetypes` — GET open to any project member; POST (add/delete)
    requires editor+ (`can_manage_vocabulary`).
  - `DashboardView` — `get_queryset` / `map_images` via
    `Project.objects.visible_to(request.user)`; delete `_visible_projects` and
    the username list.
  - `fetchProjects` — same `visible_to`. *(Flagged for possible removal — see
    §8; not removed here.)*
- **`utils.py`** — remove `myprojects` (folded into the manager).

### `cpdraw/settings.py`

- `LOGIN_REDIRECT_URL = 'dashboard'` (was `/accounts/login/` — it sent
  freshly-authenticated users back to the login page).
- `LOGOUT_REDIRECT_URL = '/'`.
- `EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'` (dev; better
  in `local_settings.py`), `DEFAULT_FROM_EMAIL = 'CPDraw <noreply@cpdraw.local>'`.

---

## 4. Templates

- **`templates/registration/`** — `login.html` (extends `base.html`,
  `{{ form.as_p }}`, "Forgot password?" → `password_reset`, link to `register`);
  `password_reset_form.html`, `password_reset_done.html`,
  `password_reset_confirm.html`, `password_reset_complete.html`,
  `password_reset_email.html` + `password_reset_subject.txt`,
  `password_change_form.html`, `password_change_done.html`. All minimal, extend
  `base.html`.
- **`accounts/register.html`** — rebuild around `{{ form.as_p }}`; drop the
  hidden `first_name=n/a` / `user_type` inputs and the `WHG::` title leftover.
- **`accounts/profile.html`** — drop the hidden-`<span>` hacks and the groups
  block; render `name` / `affiliation` / `web_page` / `email` plainly; add a
  "change password" link.
- **`main/project_form.html`** (shared by create + update) — render the scope
  fields with help text ("ISO 3166-1 alpha-2, comma-separated"; "west, south,
  east, north"). `project_create.html` / `project_update.html` include it.
- **`main/dashboard.html`** / **`project_update.html`** — show/hide by role:
  "New project" (any authed user), update + delete (owner), "Add source" +
  "manage types" (editor+). Add breadcrumbs / back-links so
  dashboard → project → source → image → draw and back is a real path.
- **`main/base.html`** — replace the `javascript:{…submit()}` logout link with a
  styled submit button in the existing form. Leave the Bootstrap/jQuery/CDN
  stack alone (WO-0.6).
- **`main/index.html`** — strip the commented-out jQuery-UI autocomplete block;
  keep "Begin…" → dashboard.

---

## 5. Page & flow

```
anon → /  (index)  → Register | Login
  Register : SignupForm → create User (+ Profile via signal) → auto-login → /dashboard/
  Login    : LoginView  → /dashboard/
             Forgot password? → PasswordResetView → e-mail to the runserver console (dev)
                              → reset/<uid>/<token>/ → set new password → login

authed → /dashboard/   projects = Project.objects.visible_to(me);  Maps table below
  → "New project" → ProjectForm (title, label, uri, spatial scope*)
        → owner = me;  ProjectUser(role='owner');  seed starter vocab  → /dashboard/
  → project → /project_update/<pk>
        owner  : edit metadata + scope, delete project
        editor : add source, manage types
        → Source → MapImage → "Open" → /draw/<image_id>/
              annotator+ : draw annotations, edit own   (editor+ : edit any — WO-0.6 API rule)
  → profile → name / affiliation / web_page / email;  change password
```

`*` all scope fields optional.

---

## 6. Sequencing

1. **Model + migrations.** `main/choices.py` (`TEAMROLES` → `owner|editor|annotator`;
   remove `USERTYPES`). `Project` scope fields + `ProjectManager.visible_to` +
   permission helpers. `ProjectUser` role choices + `unique_together` + `created`
   + `creator→owner` data migration. `MapImagePlacetype` join model +
   `MapImage.available_placetypes` helper (model only — no read-path wiring, no
   UI). `Profile` drop `user_type`. Two migrations (`main`, `accounts`). One-off
   (documented in the session log, not code): `is_superuser = True` on `admin`
   and `karlg` in the dev DB.
2. **`accounts` rebuild.** `SignupForm`, `RegisterView`; swap login / logout /
   password-change / password-reset to `django.contrib.auth.views` in
   `accounts/urls.py`. Delete the `pk=5` signal, `accounts/permissions.py`, the
   `print()`s; guard `save_user_profile`. Settings: `LOGIN_REDIRECT_URL`,
   `LOGOUT_REDIRECT_URL`, `EMAIL_BACKEND`, `DEFAULT_FROM_EMAIL`.
3. **Auth templates.** `templates/registration/*` (login, 4 reset pages + email +
   subject, 2 change pages); rebuild `accounts/register.html` and
   `accounts/profile.html`.
4. **`main` views + forms.** `ProjectForm` (no `owner`; scope via
   `SimpleArrayField` + validators). `ProjectCreateView` sets owner + writes the
   `ProjectUser` row + seeds vocab. Role gates on update / delete / `add_source`
   / `project_placetypes`. `DashboardView` + `fetchProjects` → `visible_to`. Fix
   every `success_url`. Remove `myprojects`.
5. **`main` templates.** Shared `project_form.html` with scope help text;
   role-aware controls + breadcrumbs on the dashboard and project pages; strip
   `index.html`; tidy the navbar logout control.
6. **Tests.**
   - `accounts/tests.py` (currently empty): register creates `User` + `Profile`
     with `email` / `name`; duplicate username rejected; a weak password is
     rejected (`AUTH_PASSWORD_VALIDATORS` active via `UserCreationForm`); login
     redirects to `/dashboard/`; the eight auth URL names reverse; a
     `password_reset` POST renders one message to the `locmem` / console backend.
   - `main/tests/test_views.py` additions: project-create sets `owner =
     request.user`, writes `ProjectUser(role='owner')`, seeds the five starter
     placetypes; `scope_ccodes` / `scope_bbox` parse and validate (bad ccode,
     3-number bbox, `w > e` all rejected); a non-owner gets 404/403 on
     update + delete; a non-editor gets 403 on `add_source`; `visible_to` — an
     annotator sees a joined project, a stranger does not, a superuser sees all.
   - `MapImagePlacetype`: `MapImage.available_placetypes` returns the full
     project set with no rows, and exactly the linked subset with rows; deleting
     a `ProjectPlacetype` cascades the join rows away.
7. **Browser verify.** Fresh register → auto-login → dashboard. Logout → login.
   "Forgot password?" → a reset email in the `runserver` console → complete the
   reset → log in with the new password. Create a project with `scope_ccodes =
   PL, UA` and a bbox → it shows on the dashboard, the `owner` `ProjectUser` row
   exists, the starter vocab is seeded. A second (non-member) user sees neither
   the project nor its edit routes; a superuser sees every project. Walk
   index → dashboard → project → source → MapImage → `/draw/` and back, every
   link resolving.

---

## 7. Deliverable (§10 outcome)

"Existing auth, project, and map-list views wired through": register / login /
logout / password-change / password-reset are Django-conventional; project
create / update / delete and source-add enforce `owner` / `editor` roles;
project visibility is membership-based (`visible_to`); every project carries
optional spatial scope; the `index → dashboard → project → source → image →
draw` path is navigable end to end with working back-links. The Braga demo path
(login → project → Galicia recto → trace → save) works for the project owner.

---

## 8. Open questions / carried forward → WO-0.6

- **Join keys / invite flow.** `ProjectInvite` (`key`, granted `role`,
  `created_by`, nullable `expires` / `max_uses`, `uses`, `active`); owner UI on
  the project page to mint / revoke; `/join/<key>/` (auth → add `ProjectUser`,
  bump `uses`, redirect to project; anon → login/register → back). The key value
  shown once.
- **Object-level DRF permissions.** `AnnotationViewSet` — create requires project
  membership, update/delete requires `can_edit_annotation`; `ProjectPlacetypeViewSet`
  write requires editor+; list endpoints filtered by `visible_to`. Rebuild
  `accounts/permissions.py` here as project-role-aware classes consuming the
  `Project.can_*` helpers from §2.
- **Front-end library modernization** ("soon" — Karl). Bootstrap 4 → 5; drop
  jQuery / jQuery-UI where Svelte or plain JS covers it; self-host or version-pin
  CDN assets; fix the `http://ajax.googleapis.com` mixed-content stylesheet link
  in `base.html`.
- **Map-level placetype scoping — read path + UI.** The `MapImagePlacetype` table
  ships in WO-0.5; consuming it (annotation picker filtered to
  `MapImage.available_placetypes`) and the editor UI to set a map's subset come
  with the next annotation-frontend WO. A Source-level tier (one subset across a
  60-sheet atlas) is a possible middle level if it comes up — not built.
- **Read-only Source detail page.** "Metadata" links currently jump to the Django
  admin change page.
- **`fetch_projects` endpoint** — confirm anything still consumes it; likely
  removable once `visible_to` is the single source.
- **Real SMTP** + a `DEFAULT_FROM_EMAIL` on the deployment domain — deploy-time.
- **Multi-owner semantics** beyond "a co-owner can also edit" (ownership
  transfer, last-owner-leaves guard) — not needed for Phase 0.
- **Spatial-scope map-draw picker** — Phase 1, when §7a gazetteer lookup first
  consumes `Project` scope. WO-0.5 captures the fields as plain text.
