"""Builds a new Dream's content from the Blank template, under the Dream's own name (Dreams panel, New Dream).

The Blank Template (/DreamBlank/) is made by the Kit's stub generator. A copy of its assets would still point at
/DreamBlank/, and a Dream may only reference its own packages, the engine and the palette. So a new Dream is not a
copy: it is built the same way, with the same layout, under /<Name>/. This file is the one place that layout lives
for new Dreams (the generator, Scripts/EditorPython/build_dream_palette_stubs.py, builds /DreamBlank/ with the
same steps; a change to the layout belongs in both).

Needs the Dream's plugin to be mounted, which the editor only does at start-up (see dreamkit_newdream_flow).
"""
import traceback

import unreal

import dreamkit_common as common

ROOT = '/DreamPalette'
BFL = ROOT + '/API/BFL_Dream'
PRINT = '/Script/Engine.KismetSystemLibrary:PrintString'
PRINT_COLOR_KIT = '(R=0.250000,G=0.800000,B=1.000000,A=1.000000)'
TEMPLATE_ROOT = '/DreamBlank'


def _rot(pry):
    """unreal.Rotator takes (roll, pitch, yaw); the layout below is written as (pitch, yaw, roll)."""
    return unreal.Rotator(roll=pry[2], pitch=pry[0], yaw=pry[1])


# ---- graph helper (the generator's _G, trimmed to what the starter needs) ----------------------------------

class _G(object):
    def __init__(self, b, ed):
        self.b = b
        self.ed = ed
        self.bel = unreal.BlueprintEditorLibrary
        self.bgp = unreal.BlueprintGraphPin

    def names(self, node):
        return [str(self.bgp.get_pin_name(p)) for p in self.bel.list_all_pins(node)]

    def pin(self, node, name, output):
        flat = lambda t: t.replace(' ', '').replace('_', '').lower()
        pins = self.bel.list_output_pins(node) if output else self.bel.list_input_pins(node)
        for want in (lambda n: n == name, lambda n: n.startswith(name + '_'), lambda n: flat(n) == flat(name)):
            for p in pins:
                if want(str(self.bgp.get_pin_name(p))):
                    return p
        raise RuntimeError('pin %s (%s) not on %s; pins %s' % (name, 'out' if output else 'in', self.bel.get_node_title(node), self.names(node)))

    def o(self, node, name):
        return self.pin(node, name, True)

    def i(self, node, name):
        return self.pin(node, name, False)

    def link(self, a, b):
        if not self.bgp.try_create_connection(a, b):
            raise RuntimeError('cannot connect %s -> %s' % (self.bgp.get_pin_name(a), self.bgp.get_pin_name(b)))
        self.b.retry_pending()

    def d(self, src_node, src_pin, dst_node, dst_pin):
        self.link(self.o(src_node, src_pin), self.i(dst_node, dst_pin))

    def set(self, node, pin_name, value):
        p = self.i(node, pin_name)
        if 'PinCategory="wildcard"' in self.bgp.get_pin_type(p).export_text():
            self.b.pending.append((self, node, pin_name, value))
            return
        if not self.bgp.set_pin_value(p, value):
            raise RuntimeError('cannot set %s.%s = %r' % (self.bel.get_node_title(node), pin_name, value))

    def exec_out(self, node, name=None):
        if name:
            return self.o(node, name)
        p = self.bel.find_then_pin(node)
        if self.bgp.is_valid(p):
            return p
        return self.o(node, 'then')

    def exec_in(self, node):
        p = self.bel.find_execute_pin(node)
        if self.bgp.is_valid(p):
            return p
        for n in ('execute', 'exec'):
            p = self.bel.find_input_pin(node, n)
            if self.bgp.is_valid(p):
                return p
        raise RuntimeError('%s has no exec input; pins %s' % (self.bel.get_node_title(node), self.names(node)))

    def x(self, a, b, out_name=None):
        self.link(self.exec_out(a, out_name), self.exec_in(b))
        return b

    def chain(self, *nodes):
        for a, b in zip(nodes, nodes[1:]):
            self.x(a, b)
        return nodes[-1]

    def call(self, path, **values):
        n = self.ed.add_call_function_node(path)
        if not n:
            raise RuntimeError('no call node for %s' % path)
        for k, v in values.items():
            self.set(n, k, v)
        return n

    def named(self, must, must_not=(), declaring=None):
        flat = lambda s: s.lower().replace(' ', '').replace('_', '')
        hits = [n for n in self.ed.list_available_nodes([]) if all(flat(w) in flat(n) for w in must)
                and not any(flat(w) in flat(n) for w in must_not)]
        for h in hits:
            node = self.ed.create_node_from_name(h, unreal.Vector2D(0, 0), [], declaring)
            if node:
                return node
        raise RuntimeError('no creatable node with %s (candidates %s)' % (must, hits[:10]))

    def exact(self, name, declaring=None):
        node = self.ed.create_node_from_name(name, unreal.Vector2D(0, 0), [], declaring)
        if not node:
            raise RuntimeError('cannot create node %s' % name)
        return node

    def get(self, var, class_path=''):
        return self.ed.add_get_member_variable_node(var, class_path)

    def printn(self, text=None, seconds=5.0):
        n = self.call(PRINT)
        if text is not None:
            self.set(n, 'InString', text)
        self.set(n, 'bPrintToScreen', 'true')
        self.set(n, 'Duration', '%.2f' % seconds)
        self.set(n, 'TextColor', PRINT_COLOR_KIT)
        return n

    def concat(self, a=None, b_pin=None):
        n = self.call('/Script/Engine.KismetStringLibrary:Concat_StrStr')
        if a is not None:
            self.set(n, 'A', a)
        if b_pin is not None:
            self.link(b_pin, self.i(n, 'B'))
        return n


class _Builder(object):
    def __init__(self):
        self.bel = unreal.BlueprintEditorLibrary
        self.eal = unreal.EditorAssetLibrary
        self.bgp = unreal.BlueprintGraphPin
        self.pending = []
        self.lines = []

    def log(self, msg):
        self.lines.append(msg)
        common.log('new dream: ' + msg)

    def retry_pending(self, final=False):
        left = []
        for g, node, pin_name, value in self.pending:
            p = g.i(node, pin_name)
            if 'PinCategory="wildcard"' in self.bgp.get_pin_type(p).export_text():
                left.append((g, node, pin_name, value))
                continue
            if not self.bgp.set_pin_value(p, value):
                raise RuntimeError('cannot set %s.%s = %r' % (self.bel.get_node_title(node), pin_name, value))
        self.pending = left
        if final and left:
            raise RuntimeError('literal(s) never got a type')

    def cls(self, path):
        c = unreal.load_class(None, path)
        if not c:
            raise RuntimeError('class not found: %s' % path)
        return c

    def bp_class(self, asset_path):
        bp = self.eal.load_asset(asset_path)
        if not bp:
            raise RuntimeError('missing %s (is the Kit complete?)' % asset_path)
        return self.bel.generated_class(bp)

    def new_bp(self, path, parent_path):
        if self.eal.does_asset_exist(path):
            raise RuntimeError('%s already exists' % path)
        bp = self.bel.create_blueprint_asset_with_parent(path, self.cls(parent_path))
        if not bp:
            raise RuntimeError('could not create %s' % path)
        return bp

    def compile_save(self, bp):
        self.retry_pending(final=True)
        self.bel.compile_blueprint(bp)
        st = bp.get_editor_property('status')
        if st not in (unreal.BlueprintStatus.BS_UP_TO_DATE, unreal.BlueprintStatus.BS_UP_TO_DATE_WITH_WARNINGS):
            raise RuntimeError('%s did not compile (%s)' % (bp.get_path_name(), st))
        if not self.eal.save_loaded_asset(bp, False):
            raise RuntimeError('could not save %s' % bp.get_path_name())

    def graph(self, bp):
        return _G(self, unreal.BlueprintGraphEditor.get_graph_editor(self.bel.find_event_graph(bp)))

    # -- the starter Blueprint: the egg talks, the button ends the Dream ------------------------------------
    def build_starter_logic(self, plugin):
        path = '/%s/Blueprints/BP_%sStarter' % (plugin, plugin)
        bp = self.new_bp(path, '/Script/Engine.Actor')
        egg_cls = self.bp_class(ROOT + '/Items/BP_Egg')
        btn_cls = self.bp_class(ROOT + '/Devices/BP_DreamButton')
        g = self.graph(bp)
        g.ed.add_member_variable('Egg', self.bel.get_object_reference_type(egg_cls), '')
        g.ed.add_member_variable('EndButton', self.bel.get_object_reference_type(btn_cls), '')
        for v in ('Egg', 'EndButton'):
            self.bel.set_blueprint_variable_instance_editable(bp, v, True)
        self.bel.compile_blueprint(bp)
        bfl = BFL + '.' + BFL.rsplit('/', 1)[1] + '_C'
        begin = self.bel.add_event_override(bp, 'ReceiveBeginPlay', unreal.IntPoint(0, 0))
        describe = g.call(egg_cls.get_path_name() + ':DescribeEgg')
        g.d(g.get('Egg'), 'Egg', describe, 'self')
        msg = g.concat(a='Starter: the egg says: ', b_pin=g.o(describe, 'Description'))
        pr = g.printn(seconds=8.0)
        g.d(msg, 'ReturnValue', pr, 'InString')
        names = [n for n in g.ed.list_available_nodes([]) if n.endswith('|BindEventtoOnPressed') and n.startswith('Default|')]
        bind = None
        for n in names:
            bind = g.ed.create_node_from_name(n, unreal.Vector2D(1200, 0), [], btn_cls)
            if bind:
                break
        if not bind:
            raise RuntimeError('no Bind Event to OnPressed node (%s)' % names)
        g.d(g.get('EndButton'), 'EndButton', bind, 'self')
        ev = g.ed.add_custom_event_node('HandleEndButton')
        g.link(g.o(ev, 'OutputDelegate'), g.i(bind, 'Delegate'))
        show = g.call(bfl + ':ShowMessage', Seconds='4.0')
        g.set(show, 'Text', 'NSLOCTEXT("%s", "EndPressed", "You pressed End Dream. You win!")' % plugin)
        me = g.call(bfl + ':GetLocalPlayer')
        brk = g.named(['Break', 'S_DreamPlayer'])
        g.link(g.o(me, 'LocalPlayer'), self.bel.list_input_pins(brk)[0])
        arr = g.exact('Utilities|Array|MakeArray')
        g.link(g.pin(brk, 'State', True), self.bel.list_input_pins(arr)[0])
        end = g.call(bfl + ':EndDream', Outcome='Win')
        g.link(self.bel.list_output_pins(arr)[0], g.i(end, 'Winners'))
        g.chain(begin, describe, pr, bind)
        g.chain(ev, show, end)
        self.compile_save(bp)
        return bp

    # -- floor and sky: copies of the template's, so the Dream owns them -------------------------------------
    def copy_floor_and_sky(self, plugin):
        tools = unreal.AssetToolsHelpers.get_asset_tools()
        mats = {}
        for n in ('M_DreamFloor', 'M_DreamSky'):
            src = self.eal.load_asset('%s/Materials/%s' % (TEMPLATE_ROOT, n))
            if not src:
                raise RuntimeError('the Blank template has no %s' % n)
            mats[n] = tools.duplicate_asset(n, '/%s/Materials' % plugin, src)
            if not mats[n]:
                raise RuntimeError('could not copy %s' % n)
        for n, m in (('SM_DreamFloor', 'M_DreamFloor'), ('SM_DreamSky', 'M_DreamSky')):
            src = self.eal.load_asset('%s/Meshes/%s' % (TEMPLATE_ROOT, n))
            if not src:
                raise RuntimeError('the Blank template has no %s' % n)
            mesh = tools.duplicate_asset(n, '/%s/Meshes' % plugin, src)
            if not mesh:
                raise RuntimeError('could not copy %s' % n)
            mesh.set_material(0, mats[m])
            self.eal.save_loaded_asset(mesh, False)
        for m in mats.values():
            self.eal.save_loaded_asset(m, False)

    # -- the map ---------------------------------------------------------------------------------------------
    def build_map(self, plugin, starter):
        path = '/%s/Maps/Map_%s' % (plugin, plugin)
        world = unreal.EditorLoadingAndSavingUtils.new_blank_map(False)
        if not world:
            raise RuntimeError('new_blank_map failed')
        ea = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)

        def spawn(cls, loc, rot=(0, 0, 0), label=None):
            act = ea.spawn_actor_from_class(cls, unreal.Vector(*loc), _rot(rot))
            if not act:
                raise RuntimeError('could not spawn %s' % cls)
            if label:
                act.set_actor_label(label)
            return act

        floor = spawn(unreal.StaticMeshActor, (0, 0, -10), label='Dream_Floor')
        floor.static_mesh_component.set_static_mesh(unreal.load_asset('/%s/Meshes/SM_DreamFloor' % plugin))
        floor.set_actor_scale3d(unreal.Vector(20, 20, 0.2))
        sky = spawn(unreal.StaticMeshActor, (0, 0, 0), label='Dream_Sky')
        sky.static_mesh_component.set_static_mesh(unreal.load_asset('/%s/Meshes/SM_DreamSky' % plugin))
        sky.set_actor_scale3d(unreal.Vector(1000, 1000, 1000))
        sky.static_mesh_component.set_collision_profile_name('NoCollision')
        sky.static_mesh_component.set_editor_property('cast_shadow', False)
        sun = spawn(unreal.DirectionalLight, (0, 0, 500), (-35, -50, 0), 'Dream_Sun')
        sc = sun.get_component_by_class(unreal.DirectionalLightComponent)
        sc.set_mobility(unreal.ComponentMobility.MOVABLE)
        sc.set_editor_property('intensity', 4.0)
        sc.set_editor_property('cast_shadows', False)
        for i in range(4):
            spawn(unreal.PlayerStart, (-300, (i - 1.5) * 150, 2), label='Dream_PlayerStart_%d' % (i + 1))
        table = spawn(unreal.StaticMeshActor, (100, -200, 45), label='Starter_Table')
        table.static_mesh_component.set_static_mesh(unreal.load_asset('/Engine/BasicShapes/Cube'))
        table.set_actor_scale3d(unreal.Vector(0.6, 0.6, 0.9))
        egg = spawn(self.bp_class(ROOT + '/Items/BP_Egg'), (100, -200, 100), label='Starter_Egg')
        spawn(self.bp_class(ROOT + '/Entry/BP_Door_Single'), (250, 250, 0), (0, 0, 0), 'Starter_Door')
        btn = spawn(self.bp_class(ROOT + '/Devices/BP_DreamButton'), (100, 0, 0), (0, 180, 0), 'Starter_EndButton')
        label = spawn(unreal.TextRenderActor, (100, 0, 150), (0, 180, 0), 'Starter_EndButton_Label')
        trc = label.get_component_by_class(unreal.TextRenderComponent)
        trc.set_editor_property('text', unreal.Text('End Dream (Win)'))
        trc.set_editor_property('horizontal_alignment', unreal.HorizTextAligment.EHTA_CENTER)
        trc.set_editor_property('world_size', 16.0)
        logic = spawn(self.bel.generated_class(starter), (0, 0, 300), label='Starter_Logic')
        logic.set_editor_property('Egg', egg)
        logic.set_editor_property('EndButton', btn)
        if not unreal.EditorLoadingAndSavingUtils.save_map(world, path):
            raise RuntimeError('save_map failed for ' + path)
        self.log('%s saved' % path)
        return path


def build_blank(plugin):
    """Make the Blank layout under /<plugin>/. Returns (map_package, error_text); error_text is '' on success."""
    b = _Builder()
    try:
        unreal.AssetRegistryHelpers.get_asset_registry().scan_paths_synchronous(['/' + plugin, TEMPLATE_ROOT], True)
        b.copy_floor_and_sky(plugin)
        starter = b.build_starter_logic(plugin)
        path = b.build_map(plugin, starter)
        return path, ''
    except Exception:       # noqa
        return '', traceback.format_exc()
