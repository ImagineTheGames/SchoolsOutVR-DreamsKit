"""Runs when the Kit's editor starts (Unreal's Python plugin runs init_unreal.py from Content/Python).

Adds a Dreams menu with "Open the Dreams panel", opens the panel once the editor is up, and finishes a New Dream that
needed the editor to restart.
"""
import unreal

OWNER = 'DreamsCreatorKit'


@unreal.uclass()
class DreamKitOpenPanelEntry(unreal.ToolMenuEntryScript):
    @unreal.ufunction(override=True)
    def execute(self, context):
        import dreamkit_panel
        dreamkit_panel.open_panel()


def _add_menu():
    menus = unreal.ToolMenus.get()
    main = menus.find_menu('LevelEditor.MainMenu')
    if main is None:
        return False
    main.add_sub_menu(OWNER, '', 'Dreams', 'Dreams')
    entry = DreamKitOpenPanelEntry()
    entry.init_entry(OWNER, 'LevelEditor.MainMenu.Dreams', '', 'OpenDreamsPanel', 'Open the Dreams panel',
                     'New Dream, Palette, Place and Validate')
    entry.register_menu_entry()
    menus.refresh_all_widgets()
    return True


_state = {'ticks': 0, 'handle': None}


def _on_tick(_dt):
    """Wait for the editor to settle, then open the panel (and finish any pending New Dream) once."""
    _state['ticks'] += 1
    if _state['ticks'] < 90:
        return
    unreal.unregister_slate_post_tick_callback(_state['handle'])
    try:
        import dreamkit_newdream_flow as flow
        flow.resume_pending()
        import dreamkit_panel
        dreamkit_panel.open_panel()
    except Exception as e:      # noqa
        unreal.log_warning('DREAMKIT could not open the Dreams panel: %s' % e)


try:
    if _add_menu():
        unreal.log('DREAMKIT Dreams menu added')
    _state['handle'] = unreal.register_slate_post_tick_callback(_on_tick)
except Exception as e:      # noqa
    unreal.log_warning('DREAMKIT startup failed: %s' % e)
