"""New Dream wizard: name rules, descriptor, plugin skeleton and the copy of a template into Plugins/Dreams/<Name>.

Name and descriptor rules are plain Python so they can be tested without a map (see tests/test_dreamkit_newdream.py).
"""
import os
import re

import dreamkit_common as common

# Same rule as the Dreams Forge (Tools/DreamsForge/ForgeCommon.ps1, Test-DreamDescriptor): 2-32 letters, digits or _,
# starting with a letter. The title players see (Dream.Name) is a separate field of at most 24 characters.
NAME_RE = re.compile(r'^[A-Za-z][A-Za-z0-9_]{1,31}$')
TITLE_MAX = 24
TEMPLATES = ('Blank', 'Sandbox')
# Names that are already taken inside the Kit or by the engine, whatever is on disk.
RESERVED = ('DreamBlank', 'DreamSandbox', 'DreamPalette', 'Dreams', 'Dream', 'DreamKit', 'Game', 'Engine', 'Script',
            'Temp', 'Transient', 'Content', 'Config', 'Plugins', 'Saved', 'Intermediate')
_engine_plugin_names = None


def engine_plugin_names():
    """Names of every plugin the installed engine has (a Dream may not use one of them). Cached."""
    global _engine_plugin_names
    if _engine_plugin_names is None:
        import unreal
        names = set()
        root = unreal.Paths.convert_relative_path_to_full(unreal.Paths.engine_plugins_dir())
        for _d, _s, files in os.walk(root):
            for f in files:
                if f.endswith('.uplugin'):
                    names.add(f[:-len('.uplugin')].lower())
        _engine_plugin_names = names
    return _engine_plugin_names


def project_plugin_names():
    """Every plugin folder in this project (Plugins/**/<Name>.uplugin), lower case."""
    names = set()
    for _d, _s, files in os.walk(common.plugins_dir()):
        for f in files:
            if f.endswith('.uplugin'):
                names.add(f[:-len('.uplugin')].lower())
    return names


def check_name(name, taken=None):
    """Return '' when the name can be used, else one readable sentence saying what is wrong.

    taken: lower-case names already in use. When None, the engine's and the project's plugins are read.
    """
    if not name:
        return 'Type a name for your Dream.'
    bad = []
    for c in name:
        if not (c.isascii() and (c.isalnum() or c == '_')) and c not in bad:
            bad.append(c)
    if bad:
        shown = ' '.join('space' if c == ' ' else c for c in bad)
        return "'%s' has characters a Dream name cannot have (%s). Use letters, digits and _ only." % (name, shown)
    if not name[0].isalpha():
        return "'%s' must start with a letter." % name
    if len(name) < 2 or len(name) > 32:
        return "'%s' has %d characters. Use 2 to 32." % (name, len(name))
    if not NAME_RE.match(name):
        return "'%s' is not a valid Dream name. Use 2 to 32 letters, digits or _, starting with a letter." % name
    low = name.lower()
    if low in {r.lower() for r in RESERVED}:
        return "'%s' is a name the Kit uses. Pick another one." % name
    if taken is None:
        taken = engine_plugin_names() | project_plugin_names()
    if low in taken:
        return "A plugin called '%s' already exists. Pick another name." % name
    return ''


def display_title(name):
    """The title players see: the plugin name with spaces for underscores, cut to the 24 character limit."""
    return name.replace('_', ' ')[:TITLE_MAX]


def make_descriptor(name, template_uplugin, palette_sha='', kit_version='1.0'):
    """The new Dream's .uplugin as a dict, from the template's. Pure: no disk, no engine."""
    tdream = dict((template_uplugin or {}).get('Dream') or {})
    dream = {
        'KitVersion': kit_version,
        'Name': display_title(name),
        'Map': '/%s/Maps/Map_%s' % (name, name),
        'MaxPlayers': int(tdream.get('MaxPlayers', 4)),
        'MinPlayers': int(tdream.get('MinPlayers', 1)),
        'MatchSeconds': 600,
        'Realm': 'Dream',
        'HowToPlay': ['Describe how to play your Dream here.'],
        'Settings': {},
    }
    if palette_sha:
        dream['PaletteSha256'] = palette_sha
    return {
        'FileVersion': 3,
        'Version': 1,
        'VersionName': '1.0',
        'FriendlyName': display_title(name),
        'Description': "A Dream for School's Out VR made with the Dreams Creator Kit.",
        'Category': 'Dream',
        'CreatedBy': '',
        'CreatedByURL': '',
        'DocsURL': '',
        'MarketplaceURL': '',
        'SupportURL': '',
        'EnabledByDefault': False,
        'CanContainContent': True,
        'IsBetaVersion': False,
        'IsExperimentalVersion': False,
        'Installed': False,
        'Dream': dream,
    }


def write_skeleton(name, template_name, plugins_root, palette_sha='', kit_version='1.0'):
    """Create <plugins_root>/Dreams/<name>/<name>.uplugin (+ Content/Maps). Returns the .uplugin path.

    The descriptor is rewritten from the template's: KitVersion, Map, MatchSeconds 600, Realm Dream and the
    palette hash of this Kit. Pure disk work, so a test can point plugins_root at a temp folder.
    """
    tname = 'Dream' + template_name
    tpath = os.path.join(plugins_root, 'Dreams', tname, tname + '.uplugin')
    template = common.read_json(tpath, {}) or {}
    desc = make_descriptor(name, template, palette_sha, kit_version)
    if template.get('Dream', {}).get('HowToPlay') and template_name != 'Blank':
        desc['Dream']['HowToPlay'] = list(template['Dream']['HowToPlay'])[:4]
    out = os.path.join(plugins_root, 'Dreams', name, name + '.uplugin')
    common.write_json(out, desc)
    os.makedirs(os.path.join(plugins_root, 'Dreams', name, 'Content', 'Maps'), exist_ok=True)
    return out
