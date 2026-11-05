"""Shared helpers of the Dreams panel (Dreams Creator Kit, ClickUp 17tm466wdec).

Runs inside the stock Unreal Engine 5.8 editor with the stock Python plugin. Nothing here needs the game.
"""
import json
import os

import unreal

KIT_PALETTE_ROOT = '/DreamPalette'


def log(msg):
    unreal.log('DREAMKIT ' + msg)


def warn(msg):
    unreal.log_warning('DREAMKIT ' + msg)


def project_dir():
    return unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir())


def plugins_dir():
    return unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_plugins_dir())


def dreams_dir():
    return os.path.join(plugins_dir(), 'Dreams')


def docs_dir():
    return os.path.join(project_dir(), 'Docs')


def saved_dir():
    return os.path.join(project_dir(), 'Saved', 'DreamKit')


def uplugin_path(name):
    return os.path.join(dreams_dir(), name, name + '.uplugin')


def read_json(path, default=None):
    try:
        with open(path, 'r', encoding='utf-8-sig') as f:
            return json.load(f)
    except Exception:
        return default


def write_json(path, data):
    """Tabs and LF, like every other .uplugin in the Kit. ASCII only, so the file never carries a BOM."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w', encoding='utf-8', newline='\n') as f:
        json.dump(data, f, indent='\t', ensure_ascii=True)
        f.write('\n')


def list_dreams():
    """Names of the Dream plugins under Plugins/Dreams (a folder with a matching .uplugin that has a Dream block)."""
    out = []
    base = dreams_dir()
    if not os.path.isdir(base):
        return out
    for n in sorted(os.listdir(base), key=str.lower):
        d = read_json(uplugin_path(n))
        if d and isinstance(d.get('Dream'), dict):
            out.append(n)
    return out


def palette_manifest_path():
    return os.path.join(plugins_dir(), 'DreamPalette', 'Manifest', 'palette-manifest.json')


def palette_manifest():
    return read_json(palette_manifest_path(), {}) or {}


def current_map_package():
    """Package name of the map open in the editor, e.g. /EggRace/Maps/Map_EggRace, or ''."""
    try:
        world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
        return world.get_outermost().get_name() if world else ''
    except Exception:
        return ''


def dream_of_map(package_name):
    """The Dream plugin a map package belongs to (its first path element), if it is one."""
    parts = [p for p in package_name.split('/') if p]
    if parts and parts[0] in list_dreams():
        return parts[0]
    return ''
