# School's Out VR - Dreams Creator Kit

Build your own Dream for School's Out VR: a short game with its own map, rules and clock that players pick from the
Play Games screen and play with their Crew.

> **Preview.** The Kit is being built and refined. This repository will receive the Kit project and versioned
> releases as they are ready. Expect changes. The guide in `Docs/` describes the Kit as it is being built.

## What you need

- A Windows PC.
- Unreal Engine 5.8 from the Epic Games Launcher.
- About 20 GB of free disk space.
- A free mod.io account.

## Get the Kit

Download the latest zip from the **Releases** page of this repository, or clone the repository with Git LFS
installed (`git lfs install`, then `git clone`). Unzip it anywhere and double-click `DreamsCreatorKit.uproject`: it
opens in the launcher's Unreal Engine 5.8 with no compile. Press Play to try the Blank Template (WASD walk, mouse
look, left click grab / use, right click throw, Space jump).

## How it works

1. Open the Kit in Unreal Engine 5.8 and make a new Dream.
2. Build and test it in the editor.
3. Validate it, then submit it. Our Dreams Forge builds it for Windows, Quest and Steam Frame.
4. Your Dream gets its page on mod.io.

Start with [Docs/01-welcome.md](Docs/01-welcome.md).

Full guide on our website: https://imagine-games.com/games/schools-out-vr/creator-kit/ (coming soon)

## Licence

Use of the Kit is covered by the [Dreams Creator Kit Licence](LICENSE.md) (draft). The Kit is free to use for making
Dreams for School's Out VR. It is not open source.

## Changelog

- 2026-11-04: Repository created. Guide (preview) published. Kit project to follow.
- 2026-11-05: Kit v1.0.0-preview. The Kit project: the Dream Palette as stand-ins (same paths and Blueprint API as the
  game's pieces, on stock engine classes), the Blank Template Dream and a flat test player with the game's body size.
  Not yet: the Dreams panel (New Dream, Validate, Submit), the Sandbox map, and the art-kit materials.
- 2026-11-05: Kit v1.0.1-preview. New: the Dreams panel (New Dream from Blank, Place, Validate) and the Sandbox map (a 60 x 60 m lot with every device and prop). Validate is stricter (references outside the palette, out-of-date Kit, game-mode and read-only rules) and no longer warns about the height of every pedestal button and lever. Known gaps: spawner, pad and lock settings are missing in the Kit stubs, and volume devices only react to hands.
