"""New Dream wizard, the part that touches the editor (Dreams panel, Create Dream).

Why the editor restarts once: Unreal only mounts a new plugin's content folder when the editor starts, and the
stock Python API has no call that mounts one later. So Create Dream writes the plugin (descriptor, folders, an entry
in the .uproject), leaves a note, and starts the editor again. On the way back up resume_pending() builds the
Dream's content (floor, sky, starter Blueprint, map), saves it and opens the map.
"""
import os
import subprocess

import unreal

import dreamkit_common as common
import dreamkit_newdream as nd

SUPPORTED = ('Blank',)         # Task 21 adds 'Sandbox' here when the Sandbox template can be rebuilt under another name
DETACHED = 0x00000008 | 0x00000200      # DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP


def pending_path():
    return os.path.join(common.saved_dir(), 'pending-new-dream.json')


def result_path():
    return os.path.join(common.saved_dir(), 'last-new-dream.json')


def available_templates():
    return [t for t in SUPPORTED if os.path.isdir(os.path.join(common.dreams_dir(), 'Dream' + t))]


def enable_in_uproject(name):
    """Add the Dream to the .uproject's plugin list (a Dream is never enabled by default)."""
    path = unreal.Paths.convert_relative_path_to_full(unreal.Paths.get_project_file_path())
    data = common.read_json(path)
    if data is None:
        raise RuntimeError('cannot read ' + path)
    plugins = data.setdefault('Plugins', [])
    if not any(p.get('Name') == name for p in plugins):
        plugins.append({'Name': name, 'Enabled': True})
    common.write_json(path, data)


def _restart_editor():
    """Start the editor again once this one has closed, then close this one.

    The helper is a small script started through WMI, so Windows parents it outside this editor's process group
    and it survives the editor closing (a plain child process is closed with the editor).
    """
    exe = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.engine_dir()), 'Binaries', 'Win64', 'UnrealEditor.exe')
    uproject = unreal.Paths.convert_relative_path_to_full(unreal.Paths.get_project_file_path())
    q = lambda s: s.replace("'", "''")
    helper = os.path.join(common.saved_dir(), 'restart-editor.ps1')
    with open(helper, 'w', encoding='ascii', errors='replace', newline='\n') as f:
        f.write("Wait-Process -Id %d -ErrorAction SilentlyContinue -Timeout 120\n" % os.getpid())
        f.write("Start-Sleep -Seconds 3\n")
        f.write("Start-Process -FilePath '%s' -ArgumentList '\"%s\"'\n" % (q(exe), q(uproject)))
    cmd = 'powershell.exe -NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File "%s"' % helper
    launcher = ("Invoke-CimMethod -ClassName Win32_Process -MethodName Create -Arguments @{CommandLine='%s'} | Out-Null" % q(cmd))
    r = subprocess.run(['powershell.exe', '-NoProfile', '-Command', launcher], capture_output=True, text=True, timeout=30)
    common.log('restart helper started: exit %s %s' % (r.returncode, (r.stdout + r.stderr).strip()[:200]))
    unreal.SystemLibrary.quit_editor()


def create(name, template, restart=True):
    """Make the plugin for a new Dream and (unless restart is False) restart the editor. Returns (ok, message)."""
    msg = nd.check_name(name)
    if msg:
        return False, msg
    if template not in available_templates():
        return False, 'The %s template is not in this Kit yet. Start from Blank.' % template
    unreal.EditorLoadingAndSavingUtils.save_dirty_packages(True, True)
    manifest = common.palette_manifest()
    try:
        nd.write_skeleton(name, template, common.plugins_dir(), manifest.get('sha256', ''), str(manifest.get('kitVersion', '1.0')))
        enable_in_uproject(name)
        common.write_json(pending_path(), {'name': name, 'template': template})
    except Exception as e:      # noqa
        return False, 'Could not create the Dream: %s' % e
    common.log('created plugin %s from %s; restart %s' % (name, template, restart))
    if restart:
        _restart_editor()
    return True, 'Created %s. The editor restarts now to load it, then your map opens.' % name


def _record(name, ok, message):
    common.write_json(result_path(), {'name': name, 'ok': ok, 'message': message})


def resume_pending():
    """Finish a New Dream after the restart. Safe to call every start-up: it does nothing without a note."""
    pend = common.read_json(pending_path())
    if not pend:
        return
    name = pend.get('name', '')
    try:
        os.remove(pending_path())
    except OSError:
        pass
    try:
        if not unreal.PluginBlueprintLibrary.is_plugin_mounted(name):
            _record(name, False, '%s was not loaded by the editor. Check that Plugins/Dreams/%s exists and restart the editor.' % (name, name))
            return
        import dreamkit_blank
        map_pkg, err = dreamkit_blank.build_blank(name)
        if err:
            common.warn('new dream failed:\n' + err)
            _record(name, False, 'The Dream %s was made but its map could not be built: %s' % (name, err.strip().splitlines()[-1]))
            return
        unreal.EditorAssetLibrary.save_directory('/' + name, False, True)
        unreal.EditorLoadingAndSavingUtils.load_map(map_pkg)
        _record(name, True, 'Your Dream %s is ready and its map is open. Place pieces from the Palette.' % name)
        common.log('new dream %s ready' % name)
    except Exception as e:      # noqa
        common.warn('new dream failed: %s' % e)
        _record(name, False, 'The Dream %s could not be finished: %s' % (name, e))


def pop_result():
    """The note resume_pending() left for the panel: (name, ok, message) or None. Reading it removes it."""
    r = common.read_json(result_path())
    if r:
        try:
            os.remove(result_path())
        except OSError:
            pass
        return r.get('name', ''), bool(r.get('ok')), r.get('message', '')
    return None
