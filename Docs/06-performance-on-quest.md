# Performance on Quest

Many players will try your Dream on a Quest 3. A Quest is a phone-class chip that draws two screens at a high
frame rate. A map that looks fine in your editor can run badly on it.

The Validate button checks the limits below. A **FAIL** stops your Dream from being built. A **WARN** lets it
through but a reviewer will look at it.

These numbers come from our own tests. We may adjust them a little after more testing on real headsets.
We will list any change in the release notes.

## The limits

| Check | Limit | Why |
| --- | --- | --- |
| File size, per platform | FAIL over 250 MB, WARN over 100 MB | Players download your Dream on the headset. A small file starts fast. A fully dressed classroom is about 30 MB. |
| Triangles in the whole map | FAIL over 600,000, WARN over 350,000 | The Playground runs well with a similar load at 60 to 72 frames per second. Your Dream has no crowd, but also no level-of-detail help, so we keep it lower. |
| Triangles in one mesh | FAIL over 30,000 | One huge mesh is hard to cull. Split it up. |
| Draw calls at the worst start view | WARN over 300, FAIL over 450 | Quest 3 spends most of its time on the game thread. Every extra object and material section adds work. |
| Materials and material instances | FAIL over 60 | Each new material means more shader work and more hitches. |
| See-through (translucent) materials | FAIL over 8, none larger than 4 square metres | See-through surfaces redraw the same pixels again and again. |
| Material cost on mobile | WARN over 150, FAIL over 250 | Expensive materials slow every pixel. |
| Textures | FAIL if a side is over 2048 or not a power of two. WARN over 200 MB in total | Headset memory is small. |
| Lights | One movable directional light. Up to 4 point or spot lights, with no shadows. FAIL on any Static or Stationary light | Baked light does nothing in the game, so a Static light leaves your room dark. |
| Niagara effects | FAIL over 6 in the map, over 500 particles each, or any GPU simulation | Particles cost a lot on Quest. |
| Actors in the map | WARN over 1,500, FAIL over 3,000 | Every actor costs a little each frame. |
| Blueprints that tick every frame | WARN over 30 | Use timers or the once-per-second event instead. |
| Skeletal meshes in the map | FAIL over 4 (the Palette janitor does not count) | Animated bodies are expensive. |
| Sounds | FAIL if one cue is over 10 MB, WARN over 50 MB in total. 3D sounds must be mono | Memory, and stereo sounds do not move in space. |
| Navigation mesh | If you place a janitor, you need a nav mesh | A janitor with no nav mesh wanders in place. |

## Things that are not allowed

These do not work well in a headset, or are not safe in a shared match.

- Scene capture and planar reflection actors.
- Decal actors. Decals are off on Quest.
- Sky atmosphere, volumetric clouds, and fog with volumetric turned on.
- Post process volumes that use blendables, Lumen or screen-space effects.
- World Partition maps.
- Static lighting of any kind.

## Habits that help

- **Light with Movable lights only.** Do not rely on baked lighting.
- **Repeat props with instanced meshes.** Use Hierarchical Instanced Static Mesh for rows of desks, lockers or
  chairs. One draw call beats fifty.
- **One material family per room.** Share materials and use material instances for colour changes.
- **Keep textures small.** 1024 is plenty for most props.
- **Avoid big see-through walls.** Glass and fog sheets are slow.
- **Use timers.** A Blueprint that checks something every frame is rarely needed.
- **Do not trust editor frame rate.** Your PC is much stronger than a Quest. A smooth editor does not mean a
  smooth headset. Validate is the first test, and a reviewer plays it on a Quest before it goes live.

## What a reviewer measures

A reviewer plays your whole match on a Quest 3. They watch for a frame rate that stays above 60 for the entire
match, no stalls longer than a tenth of a second after the first few seconds, and everything working with
both hands.
