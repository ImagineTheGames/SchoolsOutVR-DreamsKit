# Match setup

Every Dream describes itself in one small block of settings. The New Dream button fills it in for you.
You can change it later in the Dreams panel. This page explains each setting and the limits we check.

## The settings

| Setting | What it does | Limit |
| --- | --- | --- |
| Name | The title players see on the card. | 1 to 24 characters |
| Map | The map that opens when the match starts. | Must be `/<YourDream>/Maps/Map_<YourDream>` |
| MaxPlayers | The most players in one match. | 1 to 6 |
| MinPlayers | The fewest players needed to start. | 1 up to MaxPlayers |
| MatchSeconds | How long the round lasts. | 120 to 1200 seconds |
| Realm | Dream or Nightmare. See the Dreams and Nightmares page. | Dream or Nightmare |
| HowToPlay | Short lines players read before they start. | 1 to 4 lines, 90 characters each at most |
| Thumbnail | The picture on your card. | 1024 by 576 pixels |
| Settings | Your own named values, like rounds to win. | Optional |
| GameMode | A custom game mode built on the Palette's Dream game mode. | Optional |
| KitVersion | Which Kit made the Dream. The Kit writes it. | Do not edit |

Tips:

- A solo Dream is fine. Set MaxPlayers and MinPlayers to 1.
- Keep HowToPlay lines short. Players read them on a card in a headset, in many languages. Long lines get
  cut off in languages that take more room, like German and Portuguese.
- If you leave out the Thumbnail, the card shows the School's Out chalk logo.
- Most Dreams do not need a custom GameMode. Start without one.

## How players see your Dream

On the Play Games screen your Dream is a card with your thumbnail and name. The Realm badge sits first in
the row of badges. Your HowToPlay lines show in the how-to panel.

Players come in as a Crew. A Crew is up to 4 players right now. If your Dream allows 5 or 6, those extra
seats show as crossed out until the Crew limit goes up. If the Crew is bigger than your MaxPlayers, Start
Match is blocked and the card says how many players your Dream is for.

## What a Dream must have

- A map with at least as many player starts as MaxPlayers. Put them on solid ground, at least 150 cm
  apart, facing the play space.
- A complete set of settings from the table above.

That is all. You do not have to build an ending.

## How a match ends

- **The clock always ends it.** When MatchSeconds runs out, the match ends and everyone sees the recap.
- **Your Dream can end it sooner.** Call the Palette's End Dream function when someone wins or the goal is
  done. You can pass a winner or a score.
- **A janitor can end it.** If your Dream has a janitor and every player is caught, the match ends.
- **If the host leaves,** the match ends, just like Prank Night.

When the match ends, everyone sees the recap board. The Continue button takes the whole Crew back to the
Playground. Nobody gets stuck: the clock, the recap and the trip home all belong to the game, not to your
Dream.

## Loot from lockers and desks

When a player smashes a locker or a desk from the Palette, it can drop a random item: a prank, slingshot
pebbles, a crowbar now and then, or a little Lunch Money. Lockers drop 35% of the time, desks 20%. The game
decides every drop, and every player sees the same item. Loot is on in every Dream unless you turn it off.

Two of your own Settings control it:

| Setting | What it does |
| --- | --- |
| `"Loot": "Off"` | No loot in your Dream. |
| `"LootItems": "<item>=<weight>, <item>=<weight>"` | Your own list of what drops, instead of ours. |

Each item in `LootItems` is the class path of a Palette item or one of your Dream's own items, then `=` and
a weight. An item with weight 20 comes up twice as often as one with 10. For example:

`"LootItems": "/DreamPalette/Items/BP_Egg.BP_Egg_C=20, /DreamPalette/Items/BP_Bat.BP_Bat_C=5"`

Lockers and desks keep their drop chances; only the items change. Anything that is not a grabbable item is
skipped, and the log says which one and why.

## Score and Lunch Money

Your Dream's score is for the board and for contests. It does not change how much Lunch Money players earn.
Lunch Money from a Dream depends on time played, with a daily limit.
