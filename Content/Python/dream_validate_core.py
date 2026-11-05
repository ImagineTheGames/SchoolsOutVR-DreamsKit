"""Dream validator core (ClickUp 17tm466wd3f), shared by the Creator Kit and the Dreams Forge.

Spec: docs/superpowers/specs/2026-11-02-dreams-creator-kit-design.md section 4.6.

STOCK ENGINE API ONLY. This file runs in the Kit (stock launcher UE 5.8, where /Script/SchoolsOut does not
exist) and in the Forge (our editor). It never imports or names a game class; palette devices are recognised
by the NAME of their class (Button, Lever, ...), which is the same on both sides because the Kit's stub palette
uses the real palette's asset names.

Entry points:
  validate_dream(plugin_name, mode, plugin_dir=None)   mode is "kit" or "forge"
  validate_root(root, map_path, mode, plugin_dir=None) same checks for any content root (used by the tests)
  write_report(result, out_dir) lives in dream_validate_report.py

What lives here: the budget and comfort checks of spec 4.6 that need only stock editor API. What stays in
Scripts/EditorPython/forge_validate_dream.py: package version probe against the fork, forbidden Blueprint
parents, the references-outside-the-Dream rule, map/lighting/navmesh/player-start checks - they need the
fork's own state or the always-cooked directory list.

Honest limits (each one is also an INFO row in the report, so a creator is not told "clean" about
something that was not looked at):
  - draw calls are ESTIMATED from material sections of components inside a 130 degree cone and 80 m of
    each player start; there is no occlusion, so it over-counts rather than under-counts.
  - mobile material instruction count is not exposed to Python on a desktop editor: INFO only.
  - light / material toggling above 3 Hz is detected only on actors that EXPOSE a rate property
    (blink_hz and friends); a Blueprint timer toggling a light is left to the human reviewer.
  - descriptor checks (name, players, MatchSeconds, thumbnail ...) need no editor and stay in the Forge's
    PowerShell pre-pass and the Kit panel; nothing was moved here.
"""
import collections
import json
import math
import os
import re
import tempfile

import unreal

Row = collections.namedtuple('Row', 'check level asset_path message')

PASS, WARN, FAIL, INFO = 'PASS', 'WARN', 'FAIL', 'INFO'

# Spec 4.6 limits, verbatim. Task 27 recalibrates them on device; change them HERE only.
LIMITS = {
    'draws_warn': 300, 'draws_fail': 450,
    'materials_fail': 60,
    'translucent_fail': 8, 'translucent_area_cm2_fail': 4.0 * 10000.0,
    'texture_warn_mb': 200.0,
    'audio_cue_fail_mb': 10.0, 'audio_total_warn_mb': 50.0,
    'tick_bp_warn': 30,
    'interact_min_cm': 60.0, 'interact_max_cm': 150.0,
    'climb_first_grip_cm': 200.0,
    'platform_cm_s': 300.0,
    'flicker_hz': 3.0,
}

# ASTC 6x6 is the Quest default: 128 bits per 36 pixels, plus about a third for the mip chain.
ASTC_BYTES_PER_PIXEL = 16.0 / 36.0
MIP_FACTOR = 4.0 / 3.0

INTERACTABLE_WORDS = ('button', 'lever', 'keyhook', 'key_hook', 'itemshelf', 'item_shelf', 'shelf')
FLICKER_PROPS = ('blink_hz', 'toggle_hz', 'flash_hz', 'flicker_hz', 'frequency_hz', 'toggle_rate_hz')
SPEED_PROPS = ('speed', 'move_speed', 'platform_speed', 'max_speed', 'velocity_cm_s')
PLATFORM_WORDS = ('platform', 'elevator', 'mover')
# Component names that are the part a hand touches. A pedestal device keeps its origin on the floor, so its height
# is the height of this part (17tm466x8a3).
INTERACTIVE_PART_WORDS = ('cap', 'handle', 'button', 'lever', 'knob', 'switch', 'grip')


# Task 22 (ClickUp 17tm466wdek). The palette is the allowlist: a Dream may reference its own packages, the
# engine, native classes and the palette. Anything else is a FAIL, in the Kit and in the Forge alike.
PALETTE_PREFIX = '/DreamPalette/'
DREAM_GAMEMODE_BP = '/DreamPalette/API/BP_DreamGameMode'
# Parent classes a Dream Blueprint may not have in v1. GameModeBase is allowed ONLY below BP_DreamGameMode.
FORBIDDEN_PARENTS = ('Pawn', 'Controller', 'GameModeBase', 'GameStateBase', 'PlayerState', 'GameInstance', 'HUD',
                     'Subsystem', 'PlayerCameraManager')
KIT_OUT_OF_DATE = 'Your kit is out of date - download Kit %s'


class ValidationResult(object):
    def __init__(self, plugin_name, mode):
        self.plugin_name = plugin_name
        self.mode = mode
        self.rows = []
        self.facts = collections.OrderedDict()

    def add(self, check, level, asset_path='', message=''):
        self.rows.append(Row(check, level, asset_path, message))
        unreal.log('DREAM-VALIDATE %s %s %s - %s' % (level, check, asset_path, message))

    @property
    def passed(self):
        return not any(r.level == FAIL for r in self.rows)

    def count(self, level):
        return sum(1 for r in self.rows if r.level == level)


# ---- small helpers -----------------------------------------------------------------------------------

def _is_a(obj, unreal_type):
    try:
        return isinstance(obj, unreal_type)
    except Exception:
        return False


def _prop(obj, name, default=None):
    try:
        return obj.get_editor_property(name)
    except Exception:
        return default


def _asset_path(a):
    return '%s.%s' % (a.package_name, a.asset_name)


def _class_names(obj):
    """Lower-case class name of an actor plus the names of its Blueprint parents, for device recognition."""
    names = []
    try:
        c = obj.get_class()
        for _ in range(8):
            if c is None:
                break
            names.append(c.get_name().lower())
            c = c.get_super_class() if hasattr(c, 'get_super_class') else None
    except Exception:
        pass
    return names


def _has_word(names, words):
    return any(w in n for n in names for w in words)


def derives_from_dream_gamemode(bp):
    """True when the Blueprint's parent chain reaches /DreamPalette/API/BP_DreamGameMode (stock API only)."""
    for _ in range(8):
        parent = unreal.BlueprintEditorLibrary.get_blueprint_parent_class(bp)
        if parent is None:
            return False
        pn = parent.get_path_name()                  # '/DreamPalette/API/BP_DreamGameMode.BP_DreamGameMode_C'
        if pn.startswith(DREAM_GAMEMODE_BP + '.'):
            return True
        if pn.startswith('/Script/'):
            return False
        bp = unreal.EditorAssetLibrary.load_asset(pn.split('.')[0])
        if bp is None or not _is_a(bp, unreal.Blueprint):
            return False
    return False


def forbidden_parent(bp):
    """Name of the forbidden engine class this Blueprint derives from, else None. A child of BP_DreamGameMode is fine."""
    parent = unreal.BlueprintEditorLibrary.get_blueprint_parent_class(bp)
    cdo = unreal.get_default_object(parent) if parent else None
    if cdo is None:
        return None
    for t in FORBIDDEN_PARENTS:
        ut = getattr(unreal, t, None)
        if ut is not None and _is_a(cdo, ut):
            if t == 'GameModeBase' and derives_from_dream_gamemode(bp):
                return None
            return t
    return None


def load_manifest(path):
    """The palette manifest as a dict, or None when the file is missing or unreadable."""
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return None


def readonly_variables(manifest):
    """{variable name: [palette asset paths]} for every palette variable whose manifest access is 'read'."""
    out = {}
    for a in (manifest or {}).get('assets', []):
        for v in a.get('variables', []) or []:
            if v.get('access') == 'read':
                out.setdefault(v['name'], []).append(a.get('path', ''))
    return out


# The exporter lists every node twice: an empty "Begin Object Class=... Name=..." declaration, then the body
# "Begin Object Name=... ExportPath=..." that carries the properties. Only the body has VariableReference.
_NODE_RE = re.compile(r'Begin Object Name="K2Node_VariableSet_\d+"[^\n]*\n(.*?)\n\s*End Object', re.S)
_VARREF_RE = re.compile(r'VariableReference=\((.*)\)')
_NAME_RE = re.compile(r'MemberName="([^"]+)"')
_OWNER_RE = re.compile(r'(/(?:DreamPalette|Script)/[A-Za-z0-9_./]+)')


def readonly_set_hits(graph_text, readonly):
    """Names of read-only palette variables that a Blueprint graph (T3D text) SETS. readonly is
    readonly_variables(manifest). A Set on a palette Blueprint variable names its declaring class as
    /DreamPalette/<...>/BP_X.BP_X_C; on the real palette the same variable is native, so the owner is a /Script/SchoolsOut
    class and only the name can be compared there. A Set with no owner is the Blueprint's own variable: never a hit."""
    hits = []
    for node in _NODE_RE.finditer(graph_text or ''):
        ref = _VARREF_RE.search(node.group(1))
        name = _NAME_RE.search(ref.group(1)) if ref else None
        if not name or name.group(1) not in readonly:
            continue
        # MemberParent reads like /Script/Engine.BlueprintGeneratedClass'/DreamPalette/X/BP_Y.BP_Y_C': several paths, so test all.
        owners = _OWNER_RE.findall(ref.group(1).replace(name.group(0), ''))
        if any(o.split('.')[0] in readonly[name.group(1)] for o in owners if o.startswith('/DreamPalette/')) or \
                any(o.startswith('/Script/SchoolsOut') for o in owners):
            hits.append(name.group(1))
    return hits


def export_graph_text(bp):
    """T3D text of a Blueprint including every graph node (stock exporter; the graph nodes are not readable from Python)."""
    fd, tmp = tempfile.mkstemp(suffix='.t3d')
    os.close(fd)
    try:
        task = unreal.AssetExportTask()
        task.object = bp
        task.filename = tmp
        task.automated = True
        task.prompt = False
        task.replace_identical = True
        task.exporter = None
        if not unreal.Exporter.run_asset_export_task(task):
            return None
        with open(tmp, 'r', encoding='utf-8', errors='replace') as f:
            return f.read()
    finally:
        try:
            os.remove(tmp)
        except OSError:
            pass


def check_readonly_sets(res, bp, path, readonly):
    """FAIL a Set node on a palette variable the manifest marks access: read. The Kit's stubs declare those as ordinary
    Blueprint variables (Python cannot make one read-only), so the Kit compiles it and only the game would refuse it."""
    if not readonly:
        return
    text = export_graph_text(bp)
    if text is None:
        res.add('read-only palette variable', INFO, path, 'could not export the graph to look for Set nodes')
        return
    for name in sorted(set(readonly_set_hits(text, readonly))):
        res.add('read-only palette variable', FAIL, path,
                '"%s" can only be read: the game sets it itself. Remove the Set node (use the device\'s functions or events instead)' % name)


def check_palette_manifest(res, dream_sha, palette_sha, palette_kit_version, mode):
    """The Dream was made against kit manifest dream_sha; this side's palette manifest is palette_sha."""
    res.facts['palette manifest sha256 (this %s)' % mode] = palette_sha or 'unknown'
    if not palette_sha:
        res.add('palette manifest', INFO, '', 'this side has no palette manifest to compare with')
    elif not dream_sha:
        res.add('palette manifest', WARN, '', 'the Dream carries no Dream.PaletteSha256, so the kit it was made with cannot be checked '
                '(made with a kit older than the check; re-create it from the current kit)')
    elif dream_sha.lower() != palette_sha.lower():
        if mode == 'forge':
            res.add('palette manifest', FAIL, '', KIT_OUT_OF_DATE % (palette_kit_version or 'latest') +
                    ' (the Dream was made against palette %s, the game has %s)' % (dream_sha[:12], palette_sha[:12]))
        else:
            res.add('palette manifest', FAIL, '', 'This Dream was made with a different Kit than this project (palette %s, this Kit %s): '
                    'copy it into a fresh download of the current Kit' % (dream_sha[:12], palette_sha[:12]))
    else:
        res.add('palette manifest', PASS, '', 'matches (%s)' % palette_sha[:12])


def check_references(res, reg, packages, root, allowed_prefixes):
    """Hard AND soft references out of the Dream. Allowed: itself, native classes, the engine, the palette and
    allowed_prefixes (the Forge passes the base game's always-cooked directories). Everything else is a FAIL."""
    opts = unreal.AssetRegistryDependencyOptions(include_soft_package_references=True,
                                                 include_hard_package_references=True,
                                                 include_searchable_names=False,
                                                 include_soft_management_references=False,
                                                 include_hard_management_references=False)
    allowed = [PALETTE_PREFIX] + [p.rstrip('/') + '/' for p in (allowed_prefixes or []) if p]
    outside_ok, bad = set(), set()
    for pkg in packages:
        for dep in reg.get_dependencies(unreal.Name(pkg), opts) or []:
            dep = str(dep)
            if dep.startswith('/Script/') or dep.startswith(root + '/'):
                continue
            if dep.startswith('/Engine/EditorResources/') or dep.startswith('/Engine/EditorMaterials/'):
                continue                # editor-only sprites; never cooked
            if dep.startswith('/Engine/') or any(dep.startswith(p) for p in allowed):
                outside_ok.add(dep)
                continue
            bad.add('%s -> %s' % (pkg, dep))
    res.facts['references into the palette / base game (allowed)'] = len(outside_ok)
    for b in sorted(bad)[:40]:
        res.add('reference outside the palette', FAIL, b.split(' -> ')[0],
                'uses %s, which is not part of the Dream Palette. Only the palette, the engine and your own assets may be used: '
                'replace it with a palette asset or import your own copy into the Dream' % b.split(' -> ')[1])
    if len(bad) > 40:
        res.add('reference outside the palette', FAIL, '', '... and %d more' % (len(bad) - 40))
    if not bad:
        res.add('reference outside the palette', PASS, '', '%d, all engine or palette' % len(outside_ok))


def find_plugin_dir(plugin_name):
    """The Dream's plugin folder: the Forge's env var, else the project's Plugins tree."""
    env = os.environ.get('FORGE_PLUGIN_DIR', '')
    if env and os.path.isdir(env):
        return env
    base = unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_plugins_dir())
    for root, _dirs, files in os.walk(base):
        if plugin_name + '.uplugin' in files:
            return root
    return ''


def _disk_bytes(package_name, plugin_dir, root):
    """Bytes on disk of a package (.uasset + .uexp + .ubulk): the editor-side size, an upper bound of the pak."""
    rel = package_name[len(root):].lstrip('/')
    if package_name.startswith('/Game/'):
        base = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_content_dir()), package_name[len('/Game/'):])
    elif plugin_dir:
        base = os.path.join(plugin_dir, 'Content', rel)
    else:
        return 0
    total = 0
    for ext in ('.uasset', '.umap', '.uexp', '.ubulk'):
        p = base + ext
        if os.path.isfile(p):
            total += os.path.getsize(p)
    return total


def _blend_mode(mat):
    """Blend mode of a material or a material instance chain (instance override first, then the parent)."""
    for _ in range(16):
        if mat is None:
            return None
        if _is_a(mat, unreal.Material):
            return _prop(mat, 'blend_mode')
        if _is_a(mat, unreal.MaterialInstance):
            ov = _prop(mat, 'base_property_overrides')
            if ov is not None and _prop(ov, 'override_blend_mode'):
                return _prop(ov, 'blend_mode')
            mat = _prop(mat, 'parent')
            continue
        return None
    return None


def _is_translucent(mat):
    bm = _blend_mode(mat)
    return bm is not None and bm == unreal.BlendMode.BLEND_TRANSLUCENT


def _interactive_point(actor):
    """World location a hand reaches on this device: the highest component whose name says it is the touched part
    (button cap, lever handle), else the actor origin."""
    best = None
    try:
        comps = actor.get_components_by_class(unreal.SceneComponent) or []
    except Exception:
        comps = []
    for c in comps:
        try:
            name = c.get_name().lower()
            if not any(w in name for w in INTERACTIVE_PART_WORDS):
                continue
            loc = c.get_world_location()
        except Exception:
            continue
        if best is None or loc.z > best.z:
            best = loc
    return best if best is not None else actor.get_actor_location()


def _floor_z(world, actor, loc=None):
    """Z of the first visible surface straight below loc (default the actor origin), or None when nothing is hit."""
    if loc is None:
        loc = actor.get_actor_location()
    try:
        hit = unreal.SystemLibrary.line_trace_single(world, loc, loc - unreal.Vector(0, 0, 600),
                                                     unreal.TraceTypeQuery.ECC_VISIBILITY, False, [actor],
                                                     unreal.DrawDebugTrace.NONE, True)
    except Exception:
        return None
    if hit is None:
        return None
    try:
        t = hit.to_tuple()          # (blocking_hit, initial_overlap, time, distance, location, impact_point, ...)
        return t[5].z if t[0] else None
    except Exception:
        return None


# ---- asset checks ------------------------------------------------------------------------------------

def check_assets(res, assets, root, plugin_dir, readonly=None):
    mats = []
    translucent = []
    tex_bytes = 0
    audio = []
    tick_bps = []
    for a in assets:
        cls = str(a.asset_class_path.asset_name)
        path = _asset_path(a)
        if cls not in ('Material', 'MaterialInstanceConstant', 'Texture2D', 'SoundWave', 'Blueprint'):
            continue
        obj = unreal.EditorAssetLibrary.load_asset(path)
        if obj is None:
            continue                # the Forge's own check reports a load failure
        if _is_a(obj, unreal.MaterialInterface):
            mats.append(path)
            if _is_translucent(obj):
                translucent.append(path)
        elif _is_a(obj, unreal.Texture2D):
            x, y = obj.blueprint_get_size_x(), obj.blueprint_get_size_y()
            tex_bytes += x * y * ASTC_BYTES_PER_PIXEL * MIP_FACTOR
        elif _is_a(obj, unreal.SoundWave):
            size = _disk_bytes(str(a.package_name), plugin_dir, root)
            channels = _prop(obj, 'num_channels', 1) or 1
            spatial = _prop(obj, 'attenuation_settings') is not None
            audio.append((path, size, channels, spatial))
        elif _is_a(obj, unreal.Blueprint):
            bad_parent = forbidden_parent(obj)
            if bad_parent == 'GameModeBase':
                res.add('Blueprint parent', FAIL, path, 'derives from GameModeBase but not from BP_DreamGameMode: a Dream game mode '
                        'must be a child of /DreamPalette/API/BP_DreamGameMode')
            elif bad_parent:
                res.add('Blueprint parent', FAIL, path, 'derives from %s (not allowed in a Dream v1)' % bad_parent)
            check_readonly_sets(res, obj, path, readonly)
            gen = _prop(obj, 'generated_class')
            if gen is None and hasattr(obj, 'generated_class'):
                try:
                    gen = obj.generated_class()
                except Exception:
                    gen = None
            cdo = unreal.get_default_object(gen) if gen is not None else None
            if cdo is not None and _is_a(cdo, unreal.Actor):
                tf = _prop(cdo, 'primary_actor_tick')
                if tf is not None and _prop(tf, 'start_with_tick_enabled') and _prop(tf, 'can_ever_tick', True):
                    tick_bps.append(path)

    # Materials + instances.
    res.facts['materials + instances'] = len(mats)
    if len(mats) > LIMITS['materials_fail']:
        res.add('materials + instances', FAIL, '', '%d (> %d): shader count and PSO hitches on Quest' % (len(mats), LIMITS['materials_fail']))
    # Translucent materials.
    res.facts['translucent materials'] = len(translucent)
    if len(translucent) > LIMITS['translucent_fail']:
        res.add('translucent materials', FAIL, translucent[0], '%d translucent materials (> %d): overdraw on mobile forward' % (len(translucent), LIMITS['translucent_fail']))
    # Mobile instruction count: not exposed on a desktop editor.
    res.add('material instruction count (mobile)', INFO, '', 'not exposed to Python on a desktop editor; a reviewer checks the heaviest materials (WARN > 150, FAIL > 250)')
    # Texture memory.
    mb = tex_bytes / (1024.0 * 1024.0)
    res.facts['texture memory (ASTC estimate)'] = '%.1f MB' % mb
    if mb > LIMITS['texture_warn_mb']:
        res.add('texture memory', WARN, '', '%.0f MB ASTC-equivalent (> %d MB)' % (mb, LIMITS['texture_warn_mb']))
    # Audio.
    total = 0.0
    for path, size, channels, spatial in audio:
        smb = size / (1024.0 * 1024.0)
        total += smb
        if smb > LIMITS['audio_cue_fail_mb']:
            res.add('audio cue size', FAIL, path, '%.1f MB (> %d MB)' % (smb, LIMITS['audio_cue_fail_mb']))
        if spatial and channels > 1:
            res.add('3D sound must be mono', FAIL, path, '%d channels with attenuation: positional sound has to be mono' % channels)
    res.facts['audio total'] = '%.1f MB in %d sounds' % (total, len(audio))
    if total > LIMITS['audio_total_warn_mb']:
        res.add('audio total', WARN, '', '%.0f MB (> %d MB)' % (total, LIMITS['audio_total_warn_mb']))
    # Blueprint actors with Tick.
    res.facts['Blueprint actors with Tick'] = len(tick_bps)
    if len(tick_bps) > LIMITS['tick_bp_warn']:
        res.add('Blueprint actors with Tick', WARN, tick_bps[0], '%d (> %d); use OnTick1s and timers' % (len(tick_bps), LIMITS['tick_bp_warn']))


# ---- map checks --------------------------------------------------------------------------------------

def _estimate_draws(world, actors):
    """Worst material-section count visible from a player start: 130 degree cone, 80 m, no occlusion."""
    starts = [a for a in actors if 'playerstart' in ' '.join(_class_names(a))]
    if not starts:
        return None, 0
    comps = []
    for a in actors:
        for c in a.get_components_by_class(unreal.MeshComponent) or []:
            try:
                b = c.get_editor_property('bounds')
                o, ext = b.origin, b.sphere_radius
                comps.append((o, ext, max(1, c.get_num_materials())))
            except Exception:
                continue
    worst = 0
    for s in starts:
        eye = s.get_actor_location() + unreal.Vector(0, 0, 160)
        fwd = s.get_actor_forward_vector()
        n = 0
        for o, radius, mats in comps:
            d = o - eye
            dist = math.sqrt(d.x * d.x + d.y * d.y + d.z * d.z)
            if dist > 8000.0 + radius:
                continue
            if dist <= radius:
                n += mats
                continue
            cosang = (d.x * fwd.x + d.y * fwd.y + d.z * fwd.z) / dist
            ang = math.degrees(math.acos(max(-1.0, min(1.0, cosang))))
            slack = math.degrees(math.asin(min(1.0, radius / dist)))
            if ang <= 65.0 + slack:
                n += mats
        worst = max(worst, n)
    return worst, len(starts)


def check_map(res, map_path, plugin_dir):
    world = unreal.EditorLoadingAndSavingUtils.load_map(map_path)
    if world is None:
        res.add('map loads', FAIL, map_path, 'the map did not load')
        return
    actors = unreal.GameplayStatics.get_all_actors_of_class(world, unreal.Actor)

    draws, nstarts = _estimate_draws(world, actors)
    if draws is None:
        res.add('estimated draw calls', INFO, '', 'no player start in the map: nothing to estimate from')
    else:
        res.facts['estimated draw calls (worst start view)'] = draws
        if draws > LIMITS['draws_fail']:
            res.add('estimated draw calls', FAIL, '', '%d at the worst of %d starts (> %d); estimate has no occlusion' % (draws, nstarts, LIMITS['draws_fail']))
        elif draws > LIMITS['draws_warn']:
            res.add('estimated draw calls', WARN, '', '%d at the worst of %d starts (> %d); estimate has no occlusion' % (draws, nstarts, LIMITS['draws_warn']))

    # Translucent surfaces larger than 4 m2: largest face of the component's scaled bounds box.
    big = []
    for a in actors:
        label = a.get_actor_label() if hasattr(a, 'get_actor_label') else a.get_name()
        for c in a.get_components_by_class(unreal.StaticMeshComponent) or []:
            mesh = _prop(c, 'static_mesh')
            if mesh is None:
                continue
            for i in range(c.get_num_materials()):
                if not _is_translucent(c.get_material(i)):
                    continue
                ext = mesh.get_bounds().box_extent
                sc = c.get_world_scale() if hasattr(c, 'get_world_scale') else unreal.Vector(1, 1, 1)
                dims = sorted([abs(ext.x * sc.x) * 2.0, abs(ext.y * sc.y) * 2.0, abs(ext.z * sc.z) * 2.0])
                area = dims[1] * dims[2]
                if area > LIMITS['translucent_area_cm2_fail']:
                    big.append((label, area))
                break
    for label, area in big:
        res.add('translucent surface', FAIL, label, '%.1f m2 (> 4 m2): translucent surfaces overdraw on mobile forward' % (area / 10000.0))

    check_comfort(res, world, actors)


def check_comfort(res, world, actors):
    unmeasured = 0
    for a in actors:
        label = a.get_actor_label() if hasattr(a, 'get_actor_label') else a.get_name()
        names = _class_names(a)
        if _has_word(names, INTERACTABLE_WORDS):
            point = _interactive_point(a)
            fz = _floor_z(world, a, point)
            if fz is None:
                unmeasured += 1
            else:
                h = point.z - fz
                if h < LIMITS['interact_min_cm'] or h > LIMITS['interact_max_cm']:
                    res.add('interactable height', WARN, label,
                            '%.0f cm over its floor; reachable things belong at 60-150 cm, biased upward' % h)
        if _has_word(names, ('climb',)):
            fz = _floor_z(world, a)
            if fz is not None:
                origin, ext = a.get_actor_bounds(False)
                grip = (origin.z - ext.z) - fz
                if grip > LIMITS['climb_first_grip_cm']:
                    res.add('climbable first grip', WARN, label, 'lowest grip is %.0f cm over the floor (> 200 cm): a player cannot reach it' % grip)
        if _has_word(names, PLATFORM_WORDS):
            for p in SPEED_PROPS:
                v = _prop(a, p)
                if isinstance(v, (int, float)) and v > LIMITS['platform_cm_s']:
                    res.add('moving platform speed', WARN, label, '%s = %.0f cm/s (> 300)' % (p, v))
        for p in FLICKER_PROPS:
            v = _prop(a, p)
            if isinstance(v, (int, float)) and v > LIMITS['flicker_hz']:
                res.add('toggle rate', WARN, label, '%s = %.1f Hz (> 3 Hz): photosensitivity' % (p, v))
    if unmeasured:
        res.add('interactable height', INFO, '', '%d interactables had no floor below them to measure from' % unmeasured)
    res.add('toggle rate', INFO, '', 'only actors that expose a rate property are measured; a Blueprint timer toggling a light is left to the reviewer')


# ---- entry points ------------------------------------------------------------------------------------

def validate_root(root, map_path, mode, plugin_dir='', allowed_prefixes=None, official=False):
    """Run every core check on one content root. map_path may be None (asset checks only).
    allowed_prefixes: extra package prefixes a reference may point into (the Forge: the base game's always-cooked
    directories). The palette and the engine are always allowed.
    official: a first-party Dream (the Forge's -AllowOfficialName): allowed /Game references, so the allowlist and the
    read-only Set check are skipped. Creator submissions (the default, and always in the Kit) get every check."""
    if mode not in ('kit', 'forge'):
        raise ValueError('mode must be "kit" or "forge", got %r' % (mode,))
    res = ValidationResult(root.strip('/'), mode)
    reg = unreal.AssetRegistryHelpers.get_asset_registry()
    reg.scan_paths_synchronous([root], True)
    assets = reg.get_assets_by_path(root, recursive=True)
    res.facts['core: assets'] = len(assets)
    check_assets(res, assets, root, plugin_dir, None if official else readonly_variables(load_manifest(palette_manifest_path())))
    if not official:
        check_references(res, reg, sorted({str(a.package_name) for a in assets}), root, allowed_prefixes)
    if map_path:
        worlds = [str(a.package_name) for a in assets if str(a.asset_class_path.asset_name) == 'World']
        if map_path not in worlds:
            res.add('map', FAIL, map_path, 'not found (maps found: %s)' % (', '.join(worlds) or 'none'))
        else:
            if len(worlds) > 1:
                res.add('map', WARN, '', 'more than one map in the Dream: %s' % ', '.join(worlds))
            check_map(res, map_path, plugin_dir)
    return res


def palette_manifest_path():
    return os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_plugins_dir()),
                        'DreamPalette', 'Manifest', 'palette-manifest.json')


def read_descriptor(plugin_name, plugin_dir):
    """The Dream block of <plugin_dir>/<plugin_name>.uplugin, or {}."""
    try:
        with open(os.path.join(plugin_dir, plugin_name + '.uplugin'), 'r', encoding='utf-8-sig') as f:
            return json.load(f).get('Dream') or {}
    except Exception:
        return {}


def validate_dream(plugin_name, mode, plugin_dir=None, allowed_prefixes=None, official=False):
    """The whole core validation of one Dream plugin, by name. Returns a ValidationResult.
    Env FORGE_PALETTE_SHA256 / FORGE_PALETTE_KIT_VERSION override the manifest read from the project (the Forge)."""
    root = '/' + plugin_name
    plugin_dir = plugin_dir or find_plugin_dir(plugin_name)
    res = validate_root(root, '%s/Maps/Map_%s' % (root, plugin_name), mode, plugin_dir, allowed_prefixes, official)
    res.plugin_name = plugin_name
    if official:
        res.add('official Dream', INFO, '', 'NOTE: first-party Dream, creator checks skipped (palette allowlist, kit hash, read-only Set); the game-mode rule still applies')
        return res
    manifest = load_manifest(palette_manifest_path())
    sha = os.environ.get('FORGE_PALETTE_SHA256') or (manifest or {}).get('sha256') or ''
    kit_version = os.environ.get('FORGE_PALETTE_KIT_VERSION') or (manifest or {}).get('kitVersion') or ''
    dream = read_descriptor(plugin_name, plugin_dir) if plugin_dir else {}
    check_palette_manifest(res, str(dream.get('PaletteSha256') or ''), sha, kit_version, mode)
    return res
