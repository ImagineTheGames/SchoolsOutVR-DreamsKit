# Troubleshooting

When Validate or the Dreams Forge finds a problem, it tells you which asset and why. Here are the ten you are
most likely to see. Each one shows part of the real message, so you can match it, and then what to do.

Messages show in the Dreams panel and in the report. A report line starts with FAIL, WARN or PASS. A FAIL
must be fixed. A WARN is a heads-up.

## 1. "Saved by a newer Unreal"

Message: "was saved by a newer Unreal 5.8 hotfix than the kit supports"

Your Unreal Engine is a newer 5.8 update than the one the Kit is made for. The panel names the version to use.
Install that version from the Epic launcher, open your Dream in it, save it again and submit. The Kit also
warns you about this before it uploads anything.

## 2. A reference outside your Dream

Message: "is being referenced by DLC"

The report check is called "reference outside the Dream". Something in your Dream uses an asset that is not
yours and is not in the game. The line names the asset. Replace it with a Palette piece or an engine basic
shape, or copy the asset into your own Dream folder if it is yours to share.

## 3. Not enough player starts

Message: "placed, MaxPlayers is"

The full line reads like "2 placed, MaxPlayers is 4". Add more player starts until you have at least as many
as MaxPlayers. Put each on solid ground, at least 150 cm from the others. Another check, "player start floor",
fails when a start floats more than 20 cm above the ground.

## 4. A Blueprint will not compile

If a Blueprint that calls a Palette piece shows a red compile error in the editor, the call is out of date
or the wrong type. Open the Blueprint, fix the node, and compile it until it is clean. Validate reports
Blueprints that do not compile as FAIL, and the Forge will not build them.

## 5. A janitor with no navigation mesh

Message: "a janitor is placed but there is no NavMeshBoundsVolume"

A janitor needs a floor to walk on. Add a Nav Mesh Bounds Volume that covers the walkable area, then press
P in the editor to check that the floor turns green.

## 6. The file is too big

Message: "> 250 MB"

The report check is "pak size". Over 250 MB is a FAIL. Over 100 MB is a WARN. The usual cause is large
textures, long audio or too many unique meshes. Shrink textures, reuse materials and meshes, and use mono
audio for 3D sounds. See the Performance on Quest page.

## 7. The thumbnail is in the wrong place or the wrong size

Message: "must be under /"

The check is "Dream.Thumbnail". The picture has to live inside your own Dream folder. The picture should be
1024 by 576 pixels. If you leave it out, the card shows the chalk logo.

## 8. How to Play is too long

Message: "line over 90 characters"

A second message may read "1..4 lines (got" with a number. You can have from one to four lines. Keep each line
at 90 characters or fewer, so it fits on the card in every language.

## 9. A Blueprint uses a class that is not allowed

Message: "(not allowed in a Dream v1)"

The line reads "<asset> derives from <class>". Your Blueprint is built on something a Dream may not use, like
the player pawn, the player controller, the game instance or the game state. Make a new Blueprint from an
Actor or a Palette piece instead. A custom game mode must come from the Palette's Dream game mode.

## 10. The Palette changed after a Kit update

If the Kit updates and your Dream was made with an older Palette, Validate asks you to update. Open the
Dreams panel, install the new Kit, run Validate, and submit again. The Palette only adds things inside the
same major version, so your Dream keeps working.

## Other things you may see

- Name: "Dream.Name" says the name must be 1 to 24 characters.
- Players: "Dream.MaxPlayers" says the limit is 1 to 6.
- Time: "Dream.MatchSeconds" says the limit is 120 to 1200 seconds.
- Realm: "Dream.Realm" must be Dream or Nightmare.

## Still stuck?

Ask in the creator channel on the contest page, and include the report from the Dreams panel. It helps us find
the problem fast.
