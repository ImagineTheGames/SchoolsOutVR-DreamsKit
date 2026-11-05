"""The Dreams panel (Dreams Creator Kit, ClickUp 17tm466wdec).

EUW_DreamPalette is an Editor Utility Widget whose only content is a root Canvas Panel and an Event Construct that
calls on_panel_constructed(). Everything on the panel is built here, at run time, from stock UMG widgets, so the
panel stays Blueprint-and-Python only (no C++, no plugin outside a stock UE 5.8).

Tabs: Build (New Dream, Palette + Place, Validate) and Submit. Task 18 (Submit / Status) fills the Submit tab:
  - define  build_tab(panel)  in a module named  dreamkit_submit  (Content/Python); the panel calls it when it opens.
  - panel is this module's Panel object: panel.make(widget_class) creates a widget, panel.label(text) a text line,
    panel.button(text, fn) a button, panel.submit_host is the empty vertical box of the Submit tab to add to.
Nothing else in this file needs to change for Task 18.
"""
import functools
import importlib
import os

import unreal

import dreamkit_common as common

PANEL_ASSET = '/Game/DreamKit/Panel/EUW_DreamPalette'
KIT_VERSION = '1.0'

# Looks: dark chalkboard panel, light text, three accents. Kept here so the whole panel reskins in one place.
BG = (0.07, 0.08, 0.10, 1.0)
CARD = (0.12, 0.14, 0.17, 1.0)
TEXT = (0.92, 0.94, 0.96, 1.0)
DIM = (0.62, 0.68, 0.74, 1.0)
GOOD = (0.35, 0.82, 0.52, 1.0)
BAD = (1.0, 0.42, 0.38, 1.0)
WARN_C = (1.0, 0.76, 0.30, 1.0)
ACCENT = (0.22, 0.45, 0.78, 1.0)

# Palette folders players see as tabs, in this order. Folders not listed (API, ArtKit, Fonts, ...) hold no actors.
GROUP_ORDER = ('Pranks', 'Breakables', 'Entry', 'Devices', 'Climbing', 'Janitor', 'Nightmare', 'Spawning')
HIDDEN_GROUPS = ('API', 'ArtKit')
GUIDE_FILE = '01-welcome.md'

_panel = None          # the live Panel, if the window is open
_last_validation = None   # the last Validate answer, drawn again if the panel is rebuilt


def _lc(rgba):
    return unreal.LinearColor(*rgba)


def _slate_color(rgba):
    sc = unreal.SlateColor()
    sc.specified_color = _lc(rgba)        # the default rule of a new SlateColor is "use the specified colour"
    return sc


# ---- deferred work ---------------------------------------------------------------------------------------

_deferred = []
_tick_handle = None


def _tick(_dt):
    global _tick_handle
    if not _deferred:
        if _tick_handle is not None:
            unreal.unregister_slate_post_tick_callback(_tick_handle)
            _tick_handle = None
        return
    due = []
    for item in _deferred:
        item[0] -= 1
        if item[0] <= 0:
            due.append(item)
    for item in due:
        _deferred.remove(item)
        try:
            item[1]()
        except Exception as e:      # noqa
            common.warn('deferred call failed: %s' % e)


def defer(fn, ticks=3):
    """Run fn a few editor frames from now, so the panel repaints (for example 'Validating...') before fn blocks."""
    global _tick_handle
    _deferred.append([ticks, fn])
    if _tick_handle is None:
        _tick_handle = unreal.register_slate_post_tick_callback(_tick)


# ---- opening ---------------------------------------------------------------------------------------------

def open_panel():
    """Open (or focus) the Dreams panel tab."""
    bp = unreal.EditorAssetLibrary.load_asset(PANEL_ASSET)
    if bp is None:
        common.warn('the panel asset %s is missing' % PANEL_ASSET)
        return
    unreal.get_editor_subsystem(unreal.EditorUtilitySubsystem).spawn_and_register_tab(bp)
    _ensure_built(0)


def on_panel_constructed():
    """Called by the panel's Event Construct (also when it is run from the Content Browser)."""
    _ensure_built(0)


def _ensure_built(attempt):
    bp = unreal.EditorAssetLibrary.load_asset(PANEL_ASSET)
    inst = unreal.get_editor_subsystem(unreal.EditorUtilitySubsystem).find_utility_widget_from_blueprint(bp) if bp else None
    if inst is None:
        if attempt < 40:
            defer(lambda: _ensure_built(attempt + 1), 3)
        else:
            common.warn('the Dreams panel did not appear')
        return
    global _panel
    root = _canvas_root(inst)
    if root is None:
        common.warn('the Dreams panel has no root canvas')
        return
    if root.get_children_count() > 0 and _panel is not None and _panel.owner_path == inst.get_path_name():
        return
    root.clear_children()
    _panel = Panel(inst, root)
    _panel.build()


def _canvas_root(inst):
    """The root Canvas Panel of the running panel widget (the only widget the asset itself holds)."""
    try:
        w = inst.find_child_widget_by_name('CanvasPanel_0')
        if w is not None:
            return w
    except Exception:
        pass
    return None


# ---- the panel -------------------------------------------------------------------------------------------

class Panel(object):
    def __init__(self, owner, root):
        self.owner = owner
        self.owner_path = owner.get_path_name()
        self.root = root
        self.dream = ''                 # the Dream the Validate button checks
        self.group = ''
        self.place_msg = None
        self.wiz_msg = None
        self.verdict = None
        self.results_box = None
        self.report_path = ''
        self.name_box = None
        self.template_box = None
        self.dream_box = None
        self.palette_box = None
        self.group_row = None
        self.pages = {}
        self.tab_buttons = {}
        self.submit_host = None
        self._keep = []

    # -- widget helpers (each returns the widget; fn arguments are plain Python) ---------------------------
    def make(self, cls):
        # No outer = the transient package: the widgets belong to this editor session only, never to the open map.
        return unreal.new_object(cls)

    def label(self, text, rgba=TEXT, size=12, wrap=True, bold=False):
        tb = self.make(unreal.TextBlock)
        tb.set_text(text)
        tb.set_color_and_opacity(_slate_color(rgba))
        font = tb.get_editor_property('font')
        font.size = size
        if bold:
            font.typeface_font_name = 'Bold'
        tb.set_font(font)
        if wrap:
            tb.set_auto_wrap_text(True)
        return tb

    def button(self, text, fn, rgba=ACCENT):
        b = self.make(unreal.Button)
        b.set_background_color(_lc(rgba))
        b.add_child(self.label(text, TEXT, 12, wrap=False, bold=True))
        # Keep the delegate wrapper (and the callable) alive: if they are collected the button silently stops firing.
        d = b.on_clicked
        d.add_callable(fn)
        self._keep.append((d, fn))
        return b

    def vbox(self):
        return self.make(unreal.VerticalBox)

    def hbox(self):
        return self.make(unreal.HorizontalBox)

    def add(self, box, widget, top=4, bottom=4, left=0, right=0, fill=False):
        if isinstance(box, unreal.HorizontalBox):
            slot = box.add_child_to_horizontal_box(widget)
        else:
            slot = box.add_child_to_vertical_box(widget)
        slot.set_padding(unreal.Margin(left, top, right, bottom))
        if fill:
            slot.set_size(unreal.SlateChildSize(1.0, unreal.SlateSizeRule.FILL))
        return slot

    def card(self, child):
        b = self.make(unreal.Border)
        b.set_brush_color(_lc(CARD))
        b.set_padding(unreal.Margin(10, 8, 10, 8))
        b.set_content(child)
        return b

    # -- layout --------------------------------------------------------------------------------------------
    def build(self):
        outer = self.make(unreal.Border)
        outer.set_brush_color(_lc(BG))
        outer.set_padding(unreal.Margin(12, 10, 12, 10))
        slot = self.root.add_child_to_canvas(outer)
        slot.set_anchors(unreal.Anchors(unreal.Vector2D(0.0, 0.0), unreal.Vector2D(1.0, 1.0)))
        slot.set_offsets(unreal.Margin(0, 0, 0, 0))

        page = self.vbox()
        outer.set_content(page)
        head = self.hbox()
        self.add(head, self.label('Dreams', TEXT, 20, wrap=False, bold=True), fill=True)
        self.add(head, self.label('Kit %s' % KIT_VERSION, DIM, 11, wrap=False), top=10)
        self.add(page, head)

        tabs = self.hbox()
        for key, text in (('build', 'Build'), ('submit', 'Submit')):
            b = self.button(text, functools.partial(self.show_tab, key))
            self.tab_buttons[key] = b
            self.add(tabs, b, right=6)
        self.add(page, tabs, bottom=8)

        scroll = self.make(unreal.ScrollBox)
        self.add(page, scroll, fill=True)
        for key in ('build', 'submit'):
            self.pages[key] = self.vbox()
            scroll.add_child(self.pages[key])
        self._build_tab()
        self._submit_tab()
        self.show_tab('build')
        self.refresh_dreams()
        self.show_group(self._groups()[0] if self._groups() else '')
        self.show_validation()
        import dreamkit_newdream_flow as flow
        done = flow.pop_result()          # a New Dream that finished while the editor was restarting
        if done:
            self.say_wizard(done[2], done[1])
            if done[1]:
                self.refresh_dreams(select=done[0])

    def show_tab(self, key):
        for k, w in self.pages.items():
            w.set_visibility(unreal.SlateVisibility.VISIBLE if k == key else unreal.SlateVisibility.COLLAPSED)
        for k, b in self.tab_buttons.items():
            b.set_background_color(_lc(ACCENT if k == key else CARD))

    # -- Build tab -----------------------------------------------------------------------------------------
    def _build_tab(self):
        page = self.pages['build']

        # 1. New Dream wizard
        wiz = self.vbox()
        self.add(wiz, self.label('1. New Dream', TEXT, 15, bold=True))
        self.add(wiz, self.label('Name your Dream and pick a start. The Kit makes the plugin, the map and the settings, then opens the map.', DIM, 11))
        row = self.hbox()
        self.add(row, self.label('Name', DIM, 12, wrap=False), right=8, top=8)
        self.name_box = self.make(unreal.EditableTextBox)
        self.name_box.set_hint_text('EggRace')
        self.add(row, self.name_box, fill=True)
        self.add(wiz, row)
        row2 = self.hbox()
        self.add(row2, self.label('Start from', DIM, 12, wrap=False), right=8, top=8)
        self.template_box = self.make(unreal.ComboBoxString)
        for t in self._templates():
            self.template_box.add_option(t)
        self.template_box.set_selected_option(self._templates()[0])
        self.add(row2, self.template_box, fill=True)
        self.add(wiz, row2)
        self.add(wiz, self.button('Create Dream', self.on_create))
        self.add(wiz, self.label('Unreal loads a new Dream only when it starts, so the editor restarts once. Your work is saved first.', DIM, 10))
        self.wiz_msg = self.label('', DIM, 11)
        self.add(wiz, self.wiz_msg)
        self.add(page, self.card(wiz), bottom=10)

        # 2. Palette
        pal = self.vbox()
        self.add(pal, self.label('2. Palette', TEXT, 15, bold=True))
        cur = self.hbox()
        self.add(cur, self.label('Working in', DIM, 12, wrap=False), right=8, top=8)
        self.dream_box = self.make(unreal.ComboBoxString)
        d = self.dream_box.on_selection_changed
        d.add_callable(self.on_dream_changed)
        self._keep.append((d, self.on_dream_changed))
        self.add(cur, self.dream_box, fill=True)
        self.add(pal, cur)
        self.group_row = self.make(unreal.WrapBox)
        self.add(pal, self.group_row)
        guide = self.hbox()
        self.group_title = self.label('', TEXT, 13, wrap=False, bold=True)
        self.add(guide, self.group_title, fill=True)
        self.add(guide, self.button('What is this?', self.on_guide, CARD))
        self.add(pal, guide, top=8)
        self.palette_box = self.make(unreal.VerticalBox)
        pal_scroll = self.make(unreal.ScrollBox)         # the list scrolls inside a fixed height so Validate stays in view
        pal_scroll.add_child(self.palette_box)
        pal_size = self.make(unreal.SizeBox)
        pal_size.set_height_override(250.0)
        pal_size.add_child(pal_scroll)
        self.add(pal, pal_size)
        self.place_msg = self.label('Pick a piece and press Place. It lands in front of the viewport camera, on the floor.', DIM, 11)
        self.add(pal, self.place_msg)
        self.add(page, self.card(pal), bottom=10)

        # 3. Validate
        val = self.vbox()
        self.add(val, self.label('3. Validate', TEXT, 15, bold=True))
        self.add(val, self.label('Checks your Dream against the limits in the guide. A FAIL must be fixed before you submit.', DIM, 11))
        vrow = self.hbox()
        self.add(vrow, self.button('Validate', self.on_validate), right=8)
        self.add(vrow, self.button('Open report', self.on_report, CARD))
        self.add(val, vrow)
        self.verdict = self.label('Not checked yet.', DIM, 14, bold=True)
        self.add(val, self.verdict, top=8)
        self.results_box = self.vbox()
        self.add(val, self.results_box)
        self.add(page, self.card(val), bottom=10)

    def _templates(self):
        import dreamkit_newdream_flow as flow
        return flow.available_templates() or ['Blank']

    def _submit_tab(self):
        page = self.pages['submit']
        host = self.vbox()
        self.submit_host = host
        self.add(page, self.card(host))
        built = False
        try:
            mod = importlib.import_module('dreamkit_submit')
            importlib.reload(mod)
            mod.build_tab(self)
            built = True
        except ImportError:
            pass
        except Exception as e:      # noqa
            common.warn('the Submit tab failed to build: %s' % e)
        if not built:
            self.add(host, self.label('Submit and Status', TEXT, 15, bold=True))
            self.add(host, self.label('Sending your Dream to the Dreams Forge and watching its status arrives in the next Kit preview. '
                                      'Until then, press Validate on the Build tab and keep your Dream folder safe.', DIM, 11))

    # -- Dreams list ---------------------------------------------------------------------------------------
    def refresh_dreams(self, select=''):
        names = common.list_dreams()
        self.dream_box.clear_options()
        for n in names:
            self.dream_box.add_option(n)
        pick = select or common.dream_of_map(common.current_map_package()) or self.dream or (names[0] if names else '')
        if pick in names:
            self.dream_box.set_selected_option(pick)
            self.dream = pick

    def on_dream_changed(self, item, _sel_type):
        self.dream = str(item)

    # -- Palette -------------------------------------------------------------------------------------------
    def _manifest_groups(self):
        """{group name: [manifest entries]} of the placeable-looking palette Blueprints (the class is checked on show)."""
        groups = {}
        for a in common.palette_manifest().get('assets', []):
            if str(a.get('kind', '')).lower() != 'blueprint':
                continue
            parts = a['path'].split('.')[0].split('/')       # ['', 'DreamPalette', Folder, Name]
            if len(parts) != 4:
                continue
            group = a.get('group') or parts[2]               # a few devices carry no group: their folder names it
            if group in HIDDEN_GROUPS:
                continue
            groups.setdefault(group, []).append(a)
        return groups

    def _groups(self):
        g = self._manifest_groups()
        return [x for x in GROUP_ORDER if x in g] + sorted(x for x in g if x not in GROUP_ORDER)

    def show_group(self, group):
        self.group = group
        self.group_row.clear_children()
        for g in self._groups():
            b = self.button(g, functools.partial(self.show_group, g), ACCENT if g == group else CARD)
            slot = self.group_row.add_child_to_wrap_box(b)
            slot.set_padding(unreal.Margin(0, 2, 6, 2))
        self.group_title.set_text(group)
        self.palette_box.clear_children()
        if not group:
            return
        import dreamkit_place
        for a in sorted(self._manifest_groups().get(group, []), key=lambda x: x['path']):
            path = a['path'].split('.')[0]
            if dreamkit_place.actor_class_of(path) is None:
                continue
            short = path.split('/')[-1]
            row = self.hbox()
            desc = (a.get('description') or '').strip()
            info = self.vbox()
            self.add(info, self.label(desc or short, DIM, 10), top=0, bottom=0)
            self.add(row, self.button("Place %s" % short, functools.partial(self.on_place, path)), right=8)
            self.add(row, info, fill=True)
            self.add(self.palette_box, row, top=3, bottom=3)

    def on_place(self, path):
        import dreamkit_place
        try:
            actor, msg = dreamkit_place.place(path)
        except Exception as e:      # noqa
            actor, msg = None, 'Place failed: %s' % e
        self.place_msg.set_text(msg)
        self.place_msg.set_color_and_opacity(_slate_color(GOOD if actor else BAD))

    def on_guide(self):
        path = os.path.join(common.docs_dir(), GUIDE_FILE)
        if os.path.isfile(path):
            os.startfile(path)
        else:
            self.place_msg.set_text('The guide page %s is not in this Kit.' % GUIDE_FILE)

    # -- New Dream -----------------------------------------------------------------------------------------
    def say_wizard(self, msg, ok):
        self.wiz_msg.set_text(msg)
        self.wiz_msg.set_color_and_opacity(_slate_color(GOOD if ok else BAD))

    def on_create(self):
        import dreamkit_newdream_flow as flow
        name = str(self.name_box.get_text()).strip()
        template = self.template_box.get_selected_option() or 'Blank'
        self.say_wizard('Creating %s ...' % name, True)
        defer(lambda: self._create_now(flow, name, template), 3)

    def _create_now(self, flow, name, template):
        ok, msg = flow.create(name, template)
        self.say_wizard(msg, ok)
        if ok:
            self.refresh_dreams(select=name)

    # -- Validate ------------------------------------------------------------------------------------------
    def on_validate(self):
        if not self.dream:
            self.verdict.set_text('Pick a Dream under "Working in" first.')
            self.verdict.set_color_and_opacity(_slate_color(BAD))
            return
        self.verdict.set_text('Validating %s ...' % self.dream)
        self.verdict.set_color_and_opacity(_slate_color(DIM))
        self.results_box.clear_children()
        defer(self._validate_now, 3)

    def _validate_now(self):
        """Run the check, remember the answer, and draw it on the panel that is on screen NOW.

        Validate opens the Dream's map, which rebuilds this panel (its widget lives in the open map's world), so the
        answer is kept in the module and drawn by whichever Panel is live afterwards.
        """
        global _last_validation
        import dreamkit_validate
        name = self.dream
        try:
            res, html = dreamkit_validate.run(name)
        except Exception as e:      # noqa
            _last_validation = {'dream': name, 'error': str(e)}
        else:
            _last_validation = {
                'dream': name, 'ok': res.passed, 'report': html, 'fails': res.count('FAIL'), 'warns': res.count('WARN'),
                'rows': [(r.level, r.check, r.asset_path, r.message) for r in res.rows if r.level in ('FAIL', 'WARN')]}
        live = _panel if _panel is not None else self
        live.show_validation()

    def show_validation(self):
        v = _last_validation
        if not v:
            return
        self.results_box.clear_children()
        if 'error' in v:
            self.verdict.set_text('Validate could not run: %s' % v['error'])
            self.verdict.set_color_and_opacity(_slate_color(BAD))
            return
        self.report_path = v['report']
        ok = v['ok']
        self.verdict.set_text('%s   %s: %d FAIL, %d WARN' % ('PASS' if ok else 'FAIL', v['dream'], v['fails'], v['warns']))
        self.verdict.set_color_and_opacity(_slate_color(GOOD if ok else BAD))
        shown = 0
        for level, rgba in (('FAIL', BAD), ('WARN', WARN_C)):
            for (lv, check, asset_path, message) in [x for x in v['rows'] if x[0] == level]:
                if shown >= 25:
                    break
                shown += 1
                row = self.hbox()
                info = self.vbox()
                self.add(info, self.label('%s  %s' % (level, check), rgba, 12, bold=True), top=0, bottom=0)
                if asset_path:
                    self.add(info, self.label(asset_path, TEXT, 11), top=0, bottom=0)
                self.add(info, self.label(message, DIM, 11), top=0, bottom=2)
                self.add(row, info, fill=True, right=8)
                if asset_path:
                    self.add(row, self.button('Show %s' % asset_path.replace(chr(92), '/').split('/')[-1].split('.')[0],
                                              functools.partial(self.on_show, asset_path), CARD))
                self.add(self.results_box, row, top=3, bottom=3)
        if ok and shown == 0:
            self.add(self.results_box, self.label('Nothing to fix. The full list is in the report.', DIM, 11))

    def on_show(self, asset_path):
        import dreamkit_validate
        if not dreamkit_validate.show_asset(asset_path):
            self.verdict.set_text('Could not find %s. It may have been moved or renamed.' % asset_path)
            self.verdict.set_color_and_opacity(_slate_color(WARN_C))

    def on_report(self):
        if self.report_path and os.path.isfile(self.report_path):
            os.startfile(self.report_path)
        else:
            self.verdict.set_text('Run Validate first; the report is written when it finishes.')
            self.verdict.set_color_and_opacity(_slate_color(DIM))
