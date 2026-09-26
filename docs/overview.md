# Overview

# Overview

The probe has landed at the bottom of the ocean depths, and through the camera you can see hundreds upon thousands
    of pearls, scattered amongst the sea floor. Deep sea dragons live here too, so in order to blend in, you and your
    team will be controlling a group of magnificent leviathan-like automata.

Each of your serpentine machines can collect pearls to grow in length; at the end of the mission, your longest robot
    (and its pearls) will be extracted back to the surface.

As such, compete with other teams to stay alive and obtain the longest dragon!

## Specifications

Each team can control up to64 dragonsat a time. Your team will write exactly one program, which
    each dragon will execute, running its owncopyof your program. A corollary of this is that
    individual dragons do not share any program memory with other dragons, and hence the only way to communicate
    dragon-to-dragon is via thesonarsystem.

Each dragon gets approximately25 millisecondsat most to compute and execute actions each turn.
    This is not entirely correct, so for more details about computational limits for each of your dragons, see theTimeoutssection.

## Gameplay

Your resident games expert notices that the interactions between these sea dragons are similar to the rules of the
    retro video gameSnake, save for some
    differences:

- These dragons can spontaneouslysplitin two.
- Dragons only communicate through long-distancesonar.
- A dragon canmove multiple timeswithin a turn, though at a cost.

## Next Steps

- You can read about the full rules of the game starting fromStructure.
- After that, feel free to started with your first bot atQuickstart!
- Some more technical information about the engine and turn order starts fromIO Protocol.
- Once you've submitted your bot to the ladder, seeELO Systemto understand rating and matches.
