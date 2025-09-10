bl_info = {
    "name": "Animation Layers",
    "author": "Your Name",
    "version": (1, 2),
    "blender": (3, 6, 9),
    "location": "NLA Editor > Sidebar > Animation Layers",
    "description": "Adds a functional layer-based animation system to Blender",
    "warning": "",
    "doc_url": "",
    "category": "Animation",
}

import bpy
from bpy.props import StringProperty, BoolProperty, FloatProperty, CollectionProperty, IntProperty, EnumProperty
from bpy.types import PropertyGroup, UIList, Operator, Panel

class AnimationLayer(PropertyGroup):
    name: StringProperty(default="New Layer")
    visible: BoolProperty(default=True, update=lambda self, context: self.update_visibility(context))
    influence: FloatProperty(default=1.0, min=0.0, max=1.0, update=lambda self, context: self.update_influence(context))
    nla_track_name: StringProperty()
    selected: BoolProperty(default=False)
    solo: BoolProperty(default=False, update=lambda self, context: self.update_solo(context))
    is_editing: BoolProperty(default=False)

    def update_visibility(self, context):
        obj = context.object
        if obj.animation_data and obj.animation_data.nla_tracks:
            track = obj.animation_data.nla_tracks.get(self.nla_track_name)
            if track:
                track.mute = not self.visible

    def update_influence(self, context):
        obj = context.object
        if obj.animation_data and obj.animation_data.nla_tracks:
            track = obj.animation_data.nla_tracks.get(self.nla_track_name)
            if track and track.strips:
                for strip in track.strips:
                    if not strip.mute:
                        strip.influence = self.influence
                        if not strip.fcurves.find('influence'):
                            strip.fcurves.new('influence')
                        strip.keyframe_insert("influence", frame=context.scene.frame_current)

    def update_solo(self, context):
        obj = context.object
        if self.solo:
            for layer in obj.animation_layers:
                if layer != self:
                    layer.visible = False
        else:
            for layer in obj.animation_layers:
                layer.visible = True

    def animate_influence(self, context, value):
        obj = context.object
        if obj.animation_data and obj.animation_data.nla_tracks:
            track = obj.animation_data.nla_tracks.get(self.nla_track_name)
            if track and track.strips:
                for strip in track.strips:
                    if not strip.mute:
                        strip.influence = value
                        strip.use_animated_influence = True
                        if strip.action:
                            fc = strip.action.fcurves.find('influence')
                            if fc is None:
                                fc = strip.action.fcurves.new('influence')
                            fc.keyframe_points.insert(frame=context.scene.frame_current, value=value)
        self.influence = value

class ANIMLAYER_UL_layers(UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname):
        if self.layout_type in {'DEFAULT', 'COMPACT'}:
            row = layout.row(align=True)
            row.prop(item, "selected", text="")
            row.prop(item, "name", text="", emboss=False)
            row.prop(item, "visible", text="", icon='HIDE_OFF' if item.visible else 'HIDE_ON', emboss=False)
            
            influence_row = row.row(align=True)
            influence_row.prop(item, "influence", text="", emboss=False, slider=True)
            
            # Add error handling for operator creation
            try:
                op = influence_row.operator("animlayer.animate_influence", text="", icon='KEY_HLT')
                if op:
                    op.layer_name = item.name
                else:
                    influence_row.label(text="", icon='ERROR')
            except Exception as e:
                print(f"Error creating animate_influence operator: {e}")
                influence_row.label(text="", icon='ERROR')
            
            row.prop(item, "solo", text="", icon='SOLO_ON' if item.solo else 'SOLO_OFF', emboss=False)

            obj = context.object
            if obj.animation_data and obj.animation_data.action:
                track = obj.animation_data.nla_tracks.get(item.nla_track_name)
                if track and track.strips and track.strips[0].action == obj.animation_data.action:
                    row.label(text="", icon='RADIOBUT_ON')

            if self.has_keyframes(context, item):
                row.label(text="", icon='KEYTYPE_KEYFRAME_VEC')

    def has_keyframes(self, context, item):
        obj = context.object
        if obj.animation_data and obj.animation_data.nla_tracks:
            track = obj.animation_data.nla_tracks.get(item.nla_track_name)
            if track and track.strips:
                for strip in track.strips:
                    if strip.action and strip.action.fcurves:
                        return True
        return False
        
class ANIMLAYER_OT_animate_influence(Operator):
    bl_idname = "animlayer.animate_influence"
    bl_label = "Animate Influence"
    bl_description = "Animate the influence of the layer"
    bl_options = {'REGISTER', 'UNDO'}

    layer_name: StringProperty()

    def execute(self, context):
        print(f"ANIMLAYER_OT_animate_influence.execute() called with layer_name: {self.layer_name}")
        obj = context.object
        layer = next((layer for layer in obj.animation_layers if layer.name == self.layer_name), None)
        if layer:
            print(f"Found layer: {layer.name}, animating influence")
            layer.animate_influence(context, layer.influence)
        else:
            print(f"Layer not found: {self.layer_name}")
        return {'FINISHED'}

class ANIMLAYER_OT_add_layer(Operator):
    bl_idname = "animlayer.add_layer"
    bl_label = "Add Animation Layer"
    bl_description = "Add a new animation layer"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        obj = context.object
        layers = obj.animation_layers
        new_layer = layers.add()
        new_layer.name = f"Layer {len(layers)}"
        
        if obj.animation_data is None:
            obj.animation_data_create()
        
        nla_tracks = obj.animation_data.nla_tracks
        new_track = nla_tracks.new(prev=None)
        new_track.name = new_layer.name
        new_layer.nla_track_name = new_track.name
        
        # Create a default action for the new layer
        new_action = bpy.data.actions.new(name=f"Action_{new_layer.name}")
        new_strip = new_track.strips.new(name=new_action.name, start=context.scene.frame_start, action=new_action)
        new_strip.blend_type = 'COMBINE'
        new_strip.use_auto_blend = False
        new_strip.influence = 1.0
        new_strip.use_animated_influence = True  # Enable animated influence by default
        
        # Set the action's blending mode to 'COMBINE'
        if obj.animation_data.action:
            obj.animation_data.action_blend_type = 'COMBINE'
        
        obj.active_animation_layer = len(layers) - 1
        return {'FINISHED'}
        
class ANIMLAYER_OT_remove_layer(Operator):
    bl_idname = "animlayer.remove_layer"
    bl_label = "Remove Animation Layer"
    bl_description = "Remove the selected animation layer"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return context.object.animation_layers

    def execute(self, context):
        obj = context.object
        layers = obj.animation_layers
        
        for i in range(len(layers) - 1, -1, -1):
            if layers[i].selected:
                if obj.animation_data:
                    nla_track = obj.animation_data.nla_tracks.get(layers[i].nla_track_name)
                    if nla_track:
                        obj.animation_data.nla_tracks.remove(nla_track)
                layers.remove(i)
        
        obj.active_animation_layer = min(obj.active_animation_layer, len(layers) - 1)
        return {'FINISHED'}

class ANIMLAYER_OT_assign_to_layer(Operator):
    bl_idname = "animlayer.assign_to_layer"
    bl_label = "Assign to Layer"
    bl_description = "Assign current animation to the active layer"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        obj = context.object
        return (obj and obj.animation_data and
                obj.animation_layers and len(obj.animation_layers) > 0)

    def execute(self, context):
        obj = context.object
        active_layer = obj.animation_layers[obj.active_animation_layer]
        
        if obj.animation_data:
            # Deactivate NLA tracks if active
            if obj.animation_data.use_tweak_mode:
                obj.animation_data.use_tweak_mode = False
            
            # If there's no current action, create a new one
            if not obj.animation_data.action:
                obj.animation_data.action = bpy.data.actions.new(name=f"Action_{active_layer.name}")
            
            current_action = obj.animation_data.action
            track = obj.animation_data.nla_tracks.get(active_layer.nla_track_name)
            
            if track:
                # Remove existing strips
                for strip in track.strips:
                    track.strips.remove(strip)
                
                # Create a new strip with the current action
                new_strip = track.strips.new(name=current_action.name, start=context.scene.frame_start, action=current_action)
                new_strip.blend_type = 'COMBINE'
                new_strip.use_auto_blend = False
                new_strip.influence = active_layer.influence
                new_strip.use_animated_influence = True

                # If we're assigning an edited action back to its original layer, replace the original action
                if "original_action_name" in active_layer:
                    original_action = bpy.data.actions.get(active_layer["original_action_name"])
                    if original_action:
                        original_action.user_remap(current_action)
                        bpy.data.actions.remove(original_action)
                    del active_layer["original_action_name"]

                # Set the action's blending mode to 'COMBINE'
                obj.animation_data.action_blend_type = 'COMBINE'

                # Clear the current action from the object
                obj.animation_data.action = None

                # Unmute the track
                track.mute = False

        return {'FINISHED'}

class ANIMLAYER_OT_edit_layer(Operator):
    bl_idname = "animlayer.edit_layer"
    bl_label = "Edit Layer Animation"
    bl_description = "Edit the animation in the selected layer"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        obj = context.object
        return obj and obj.animation_layers and len(obj.animation_layers) > 0

    def execute(self, context):
        obj = context.object
        active_layer = obj.animation_layers[obj.active_animation_layer]
        
        if obj.animation_data:
            track = obj.animation_data.nla_tracks.get(active_layer.nla_track_name)
            if track and track.strips:
                # Unlink the current action if it exists
                if obj.animation_data.action:
                    obj.animation_data.action = None
                
                # Create a copy of the strip's action and set it as the active action
                original_action = track.strips[0].action
                new_action = original_action.copy()
                new_action.name = f"{original_action.name}_edit"
                obj.animation_data.action = new_action
                
                # Set the action's blending mode to 'COMBINE'
                obj.animation_data.action_blend_type = 'COMBINE'
                
                # Mute the NLA track while editing
                track.mute = True
                
                # Store the original action name in the layer for later reference
                active_layer["original_action_name"] = original_action.name

                # Set editing state
                active_layer.is_editing = True

        return {'FINISHED'}

class ANIMLAYER_OT_merge_layers(Operator):
    bl_idname = "animlayer.merge_layers"
    bl_label = "Merge Selected Layers"
    bl_description = "Merge all selected layers into a new layer"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        obj = context.object
        return obj and obj.animation_layers and any(layer.selected for layer in obj.animation_layers)

    @staticmethod
    def get_constraint_targets(armature):
        targets = set()
        if armature.type == 'ARMATURE':
            # Add armature itself for bone-to-bone constraints
            targets.add(armature)
            
            for bone in armature.pose.bones:
                for constraint in bone.constraints:
                    # Handle bone-to-bone constraints within same armature
                    if constraint.type == 'CHILD_OF' and constraint.target == armature:
                        targets.add(armature)
        return targets

    def execute(self, context):
        obj = context.object
        animation_layers = obj.animation_layers
        scene = context.scene

        # Create animation data if none exists
        if not obj.animation_data:
            obj.animation_data_create()

        # Get all objects involved in constraints
        target_objects = self.get_constraint_targets(obj)
        
        # Directly manipulate selection without operators
        for o in context.view_layer.objects:
            o.select_set(False)
            
        obj.select_set(True)
        for o in target_objects:
            if o and o.name in context.view_layer.objects:
                o.select_set(True)
                
        context.view_layer.objects.active = obj

        # Store original state
        original_action = obj.animation_data.action if obj.animation_data else None
        original_frame = scene.frame_current
        original_tweak_mode = obj.animation_data.use_tweak_mode if obj.animation_data else False
        
        # Store and unmute all tracks during baking
        original_track_states = []
        if obj.animation_data:
            for track in obj.animation_data.nla_tracks:
                original_track_states.append((track, track.mute))
                track.mute = False  # Unmute all tracks during baking

        # Modified bake section
        if obj.type == 'ARMATURE':
            bpy.context.view_layer.objects.active = obj
            bpy.ops.object.mode_set(mode='POSE')
            bpy.ops.pose.select_all(action='SELECT')
            
            # Critical: Bake in POSE mode
            bpy.ops.nla.bake(
                frame_start=scene.frame_start,
                frame_end=scene.frame_end,
                step=1,
                only_selected=True,
                visual_keying=True,
                clear_constraints=False,
                clear_parents=False,
                use_current_action=True,
                bake_types={'POSE'}
            )
            
            bpy.ops.object.mode_set(mode='OBJECT')
        else:
            # For simple objects, bake in OBJECT mode
            bpy.ops.object.mode_set(mode='OBJECT')
            bpy.ops.nla.bake(
                frame_start=scene.frame_start,
                frame_end=scene.frame_end,
                step=1,
                only_selected=True,
                visual_keying=True,
                clear_constraints=False,
                clear_parents=False,
                use_current_action=True,
                bake_types={'OBJECT'}
            )

        # Handle case where bake didn't create an action
        merged_action = obj.animation_data.action
        if not merged_action:
            merged_action = bpy.data.actions.new(name=f"Merged_{obj.name}")
            obj.animation_data.action = merged_action

        # Create merged layer with NLA strip
        new_layer = animation_layers.add()
        new_layer.name = "Merged"
        new_track = obj.animation_data.nla_tracks.new()
        new_track.name = new_layer.name
        new_layer.nla_track_name = new_track.name

        # Create and assign the baked action
        merged_action = obj.animation_data.action
        merged_action.name = f"Merged_{obj.name}"
        new_strip = new_track.strips.new(
            name=merged_action.name,
            start=scene.frame_start,
            action=merged_action
        )
        new_strip.blend_type = 'COMBINE'

        # Remove original layers after successful merge
        layers_to_remove = [i for i, layer in enumerate(animation_layers) if layer.selected]
        for i in reversed(sorted(layers_to_remove)):
            if i < len(animation_layers):  # Prevent index errors
                track = obj.animation_data.nla_tracks.get(animation_layers[i].nla_track_name)
                if track:
                    obj.animation_data.nla_tracks.remove(track)
                animation_layers.remove(i)

        # Restore original state
        if original_action and original_action.users > 0:  # Check if still exists
            obj.animation_data.action = original_action
        else:
            obj.animation_data.action = None
            
        if obj.animation_data:
            obj.animation_data.use_tweak_mode = original_tweak_mode
            
        scene.frame_set(original_frame)
        obj.active_animation_layer = len(animation_layers) - 1

        # Restore original selection
        for o in target_objects:
            o.select_set(True)
        context.view_layer.objects.active = obj

        return {'FINISHED'}

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self)

    def draw(self, context):
        layout = self.layout
        layout.prop(self, "clean_curves")

class ANIMLAYER_OT_move_layer(Operator):
    bl_idname = "animlayer.move_layer"
    bl_label = "Move Layer"
    bl_description = "Move the selected layer up or down"
    bl_options = {'REGISTER', 'UNDO'}

    direction: EnumProperty(
        items=[
            ('UP', "Up", "Move the layer up"),
            ('DOWN', "Down", "Move the layer down"),
        ],
        name="Direction",
        description="Direction to move the layer",
        default='UP'
    )

    @classmethod
    def poll(cls, context):
        obj = context.object
        return obj and obj.animation_layers and len(obj.animation_layers) > 1

    def execute(self, context):
        obj = context.object
        layers = obj.animation_layers
        active_index = obj.active_animation_layer

        if self.direction == 'UP' and active_index > 0:
            layers.move(active_index, active_index - 1)
            obj.active_animation_layer -= 1
        elif self.direction == 'DOWN' and active_index < len(layers) - 1:
            layers.move(active_index, active_index + 1)
            obj.active_animation_layer += 1

        if obj.animation_data:
            tracks = obj.animation_data.nla_tracks
            track = tracks.get(layers[active_index].nla_track_name)
            if track:
                if self.direction == 'UP' and active_index > 0:
                    tracks.move(tracks.find(track.name), tracks.find(track.name) - 1)
                elif self.direction == 'DOWN' and active_index < len(layers) - 1:
                    tracks.move(tracks.find(track.name), tracks.find(track.name) + 1)

        return {'FINISHED'}

class ANIMLAYER_OT_exit_edit(Operator):
    bl_idname = "animlayer.exit_edit"
    bl_label = "Exit Edit Mode"
    bl_description = "Exit layer editing and save changes"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        obj = context.object
        active_layer = obj.animation_layers[obj.active_animation_layer]
        
        if obj.animation_data:
            track = obj.animation_data.nla_tracks.get(active_layer.nla_track_name)
            if track and track.strips:
                edited_action = obj.animation_data.action
                original_action_name = active_layer.get("original_action_name")
                
                if edited_action:
                    # Keep original action intact, just update the strip
                    track.strips[0].action = edited_action
                    edited_action.name = f"{original_action_name}_merged"
                    
                    # Restore original action if it exists
                    original_action = bpy.data.actions.get(original_action_name)
                    if original_action:
                        original_action.use_fake_user = True  # Protect from deletion
                    
                    # Clean up
                    obj.animation_data.action = None
                    track.mute = False
                    del active_layer["original_action_name"]
                    active_layer.is_editing = False

        return {'FINISHED'}

class ANIMLAYER_PT_main_panel(Panel):
    bl_label = "Animation Layers"
    bl_idname = "ANIMLAYER_PT_main_panel"
    bl_space_type = 'VIEW_3D'  # Changed from 'NLA_EDITOR' to 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'Animation'  # This puts it in the Animation tab of the sidebar

    @classmethod
    def poll(cls, context):
        return context.object is not None

    def draw(self, context):
        layout = self.layout
        obj = context.object

        row = layout.row()
        row.template_list("ANIMLAYER_UL_layers", "", obj, "animation_layers", obj, "active_animation_layer")

        col = row.column(align=True)
        col.operator("animlayer.add_layer", icon='ADD', text="")
        col.operator("animlayer.remove_layer", icon='REMOVE', text="")
        col.separator()
        col.operator("animlayer.move_layer", icon='TRIA_UP', text="").direction = 'UP'
        col.operator("animlayer.move_layer", icon='TRIA_DOWN', text="").direction = 'DOWN'

        if obj.animation_layers:
            layout.operator("animlayer.assign_to_layer", icon='NLA', text="Assign Current Animation to Layer")
            active_layer = obj.animation_layers[obj.active_animation_layer]
            if active_layer.is_editing:
                layout.operator("animlayer.exit_edit", icon='BACK', text="Exit Edit")
            else:
                layout.operator("animlayer.edit_layer", icon='GREASEPENCIL', text="Edit Layer Animation")
            layout.operator("animlayer.merge_layers", icon='AUTOMERGE_ON', text="Merge Selected Layers")

def register():
    bpy.utils.register_class(AnimationLayer)
    bpy.utils.register_class(ANIMLAYER_UL_layers)
    bpy.utils.register_class(ANIMLAYER_OT_add_layer)
    bpy.utils.register_class(ANIMLAYER_OT_remove_layer)
    bpy.utils.register_class(ANIMLAYER_OT_assign_to_layer)
    bpy.utils.register_class(ANIMLAYER_OT_edit_layer)
    bpy.utils.register_class(ANIMLAYER_OT_merge_layers)
    bpy.utils.register_class(ANIMLAYER_OT_move_layer)
    bpy.utils.register_class(ANIMLAYER_OT_exit_edit)
    bpy.utils.register_class(ANIMLAYER_PT_main_panel)
    bpy.utils.register_class(ANIMLAYER_OT_animate_influence)
    
    bpy.types.Object.animation_layers = CollectionProperty(type=AnimationLayer)
    bpy.types.Object.active_animation_layer = IntProperty()

def unregister():
    del bpy.types.Object.animation_layers
    del bpy.types.Object.active_animation_layer
    
    bpy.utils.unregister_class(ANIMLAYER_PT_main_panel)
    bpy.utils.unregister_class(ANIMLAYER_OT_move_layer)
    bpy.utils.unregister_class(ANIMLAYER_OT_merge_layers)
    bpy.utils.unregister_class(ANIMLAYER_OT_edit_layer)
    bpy.utils.unregister_class(ANIMLAYER_OT_assign_to_layer)
    bpy.utils.unregister_class(ANIMLAYER_OT_remove_layer)
    bpy.utils.unregister_class(ANIMLAYER_OT_add_layer)
    bpy.utils.unregister_class(ANIMLAYER_UL_layers)
    bpy.utils.unregister_class(AnimationLayer)
    bpy.utils.unregister_class(ANIMLAYER_OT_animate_influence)
    bpy.utils.unregister_class(ANIMLAYER_OT_exit_edit)

if __name__ == "__main__":
    register()