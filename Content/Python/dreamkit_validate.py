"""Validate button of the Dreams panel: descriptor checks plus the shared validator core (dream_validate_core).

dream_validate_core.py and dream_validate_report.py are COPIES of Scripts/EditorPython/ in the game's depot, put here
by Tools/Build-DreamsKit.ps1; the Dreams Forge runs the same files, so a Dream that passes here is not surprised later.
"""
import os

import unreal

import dreamkit_common as common

FAIL, WARN, INFO, PASS = 'FAIL', 'WARN', 'INFO', 'PASS'
HOW_TO_LINE_MAX = 90
THUMB_W, THUMB_H = 1024, 576


def check_descriptor(res, name, plugin_dir):
    """The Dream block of <Name>.uplugin against the limits in Docs/05-match-setup.md. Rows point at the .uplugin."""
    rel = 'Plugins/Dreams/%s/%s.uplugin' % (name, name)
    data = common.read_json(os.path.join(plugin_dir, name + '.uplugin'))
    if data is None:
        res.add('descriptor', FAIL, rel, 'The .uplugin file is missing or is not valid JSON.')
        return
    d = data.get('Dream')
    if not isinstance(d, dict):
        res.add('descriptor', FAIL, rel, 'The .uplugin has no "Dream" block. Make the Dream with the New Dream button.')
        return

    def fail(key, msg):
        res.add('Dream.' + key, FAIL, rel, msg)

    ok = True
    title = d.get('Name')
    if not isinstance(title, str) or not (1 <= len(title) <= 24):
        fail('Name', 'Name is %r. It must be 1 to 24 characters.' % (title,)); ok = False
    expect_map = '/%s/Maps/Map_%s' % (name, name)
    if d.get('Map') != expect_map:
        fail('Map', 'Map is %r. It must be %s.' % (d.get('Map'), expect_map)); ok = False
    mx = d.get('MaxPlayers')
    if not isinstance(mx, int) or not (1 <= mx <= 6):
        fail('MaxPlayers', 'MaxPlayers is %r. It must be a whole number from 1 to 6.' % (mx,)); ok = False
    mn = d.get('MinPlayers', 1)
    if not isinstance(mn, int) or not (1 <= mn <= (mx if isinstance(mx, int) else 6)):
        fail('MinPlayers', 'MinPlayers is %r. It must be from 1 up to MaxPlayers.' % (mn,)); ok = False
    sec = d.get('MatchSeconds')
    if not isinstance(sec, int) or not (120 <= sec <= 1200):
        fail('MatchSeconds', 'MatchSeconds is %r. It must be 120 to 1200 seconds.' % (sec,)); ok = False
    if d.get('Realm') not in ('Dream', 'Nightmare'):
        fail('Realm', 'Realm is %r. It must be Dream or Nightmare.' % (d.get('Realm'),)); ok = False
    kv = str(d.get('KitVersion', ''))
    if not kv.startswith('1.'):
        fail('KitVersion', 'KitVersion is %r. This Kit makes Dreams for kit 1.x.' % kv); ok = False
    lines = d.get('HowToPlay')
    if not isinstance(lines, list) or not (1 <= len(lines) <= 4):
        fail('HowToPlay', 'HowToPlay needs 1 to 4 short lines.'); ok = False
    else:
        for line in lines:
            if not isinstance(line, str):
                fail('HowToPlay', 'HowToPlay lines must be text.'); ok = False
            elif len(line) > HOW_TO_LINE_MAX:
                res.add('Dream.HowToPlay', WARN, rel, 'A HowToPlay line has %d characters. Keep each under %d so it fits the card.' % (len(line), HOW_TO_LINE_MAX))
    thumb = d.get('Thumbnail')
    if thumb:
        if not isinstance(thumb, str) or not thumb.startswith('/%s/' % name):
            fail('Thumbnail', 'Thumbnail must be a picture inside your Dream (/%s/...).' % name); ok = False
        else:
            tex = unreal.EditorAssetLibrary.load_asset(thumb.split('.')[0])
            if tex is None:
                fail('Thumbnail', 'Thumbnail %s was not found.' % thumb); ok = False
            elif hasattr(tex, 'blueprint_get_size_x') and (tex.blueprint_get_size_x(), tex.blueprint_get_size_y()) != (THUMB_W, THUMB_H):
                fail('Thumbnail', 'Thumbnail is %dx%d. It must be %dx%d.' % (tex.blueprint_get_size_x(), tex.blueprint_get_size_y(), THUMB_W, THUMB_H)); ok = False
    if ok:
        res.add('descriptor', PASS, rel, 'name, map, players, time, realm and how-to-play are within the limits')


def run(name):
    """Validate one Dream in the open editor. Returns (ValidationResult, html_report_path).

    It saves what you have open first (the validator loads the Dream's map), and puts the map you had open back after.
    """
    import importlib
    import dream_validate_core as core
    import dream_validate_report as report
    importlib.reload(core)
    importlib.reload(report)

    plugin_dir = os.path.join(common.dreams_dir(), name)
    previous = common.current_map_package()
    unreal.EditorLoadingAndSavingUtils.save_dirty_packages(True, True)
    common.log('validating %s' % name)
    res = core.validate_dream(name, 'kit', plugin_dir)
    check_descriptor(res, name, plugin_dir)
    out_dir = os.path.join(common.project_dir(), 'Saved', 'DreamReports', name)
    html, _json = report.write_report(res, out_dir)
    common.log('validation %s: %d FAIL, %d WARN. Report %s' % ('PASS' if res.passed else 'FAIL', res.count('FAIL'), res.count('WARN'), html))
    if previous and previous != '/Temp/Untitled_1':
        try:
            mapname = previous.split('.')[0]
            if common.current_map_package() != mapname:
                unreal.EditorLoadingAndSavingUtils.load_map(mapname)
        except Exception as e:
            common.warn('could not reopen %s: %s' % (previous, e))
    return res, html


def show_asset(asset_path):
    """Point the editor at what a result row names: an asset in the Content Browser, or an actor in the map."""
    if not asset_path:
        return False
    if asset_path.startswith('/'):
        pkg = asset_path.split('.')[0]
        if unreal.EditorAssetLibrary.does_asset_exist(pkg):
            unreal.EditorAssetLibrary.sync_browser_to_objects([pkg])
            return True
        return False
    ea = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    hits = [a for a in ea.get_all_level_actors() if a.get_actor_label() == asset_path or a.get_name() == asset_path]
    if hits:
        ea.set_selected_level_actors(hits[:1])
        return True
    if asset_path.endswith('.uplugin') or 'Plugins/' in asset_path:
        folder = os.path.join(common.project_dir(), os.path.dirname(asset_path).replace('/', os.sep))
        if os.path.isdir(folder):
            os.startfile(folder)
            return True
    return False
