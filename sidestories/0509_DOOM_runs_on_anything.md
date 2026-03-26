# DOOM runs on anything

*Source: https://forums.spacebattles.com/threads/ghost-in-the-city-cyberpunk-gamer-si.1046809/page-1372#post-96426953*
*Words: ~660*

---

*   [](https://forums.spacebattles.com/threads/ghost-in-the-city-cyberpunk-gamer-si.1046809/page-1372#post-96426953)
*   [#34,296](https://forums.spacebattles.com/threads/ghost-in-the-city-cyberpunk-gamer-si.1046809/page-1372#post-96426953)

**DOOM runs on anything**

* * *

Mokoto was sure Sasha would be impressed with her newest Quickhack!

 Mokoto's apathy towards rep hadn't changed. She didn't start going to bars and boasting to groupies and civvies. But! Mokoto was tired of her peers treating her like a kid. Maine's and even Sasha's dismissal had tugged at her pride something fierce—was it not enough she was saving the catgirl? Must she be humiliated too?

 No!

 Thus there was only one option! Sasha had been impressed with her debugging skills. Sasha would bow before Mokoto's original work!

 The robots favored by the big corporations were impressive. Grunts who dreamed of being edgerunners and gonks who believed themselves to be so were no match to calculated murder. Their frames were purpose-built to handle recoil, their minds cared not for casualties or surprises, and their ICE was the best work of a team of corpo netrunners.

 And yet… they weren't Mokoto!

 Mokoto had learned of a terrible zero-day bug while sleuthing in the Net. It was not something most would understand. Netrunners were self-taught these days, open-source projects were a laughable idea to anyone not in school, and the only classes available were overpriced and made by corpos. Few were taught race conditions properly. The initialization of a multi-threaded process—the start-up order of a program running multiple functions in parallel—was not thought to be a goldmine for hacking. They were fools.

 They were gonks who would surely be in awe of Mokoto's deviousness!

 Mokoto nodded to herself, eyes flickering over her new program. It even compiled on the first try! She ran through her explanation for the catgirl. The foundation of her hack was the protected memory a robot's optics booted from. There were several partitions to it. The one that mattered contained code generated at start-up. It took in the values of the internal systems and environment, providing immediate configuration and a procedure for the more complex code that would execute an eternity later. Well, more like half a second, but that was very long for a computer. And presented a vulnerability!

 What if, theoretically, a netrunner who looked like the Major could overwrite that initial configuration? But it wasn't theoretical—Mokoto could do that! By forcing the optics to reboot several times in quick succession, the order of initialization would be different by several milliseconds, and cause some functions to access memory that had not been written yet. They would return out-of-bound errors, preventing the optics from booting properly, before the watchdog embedded in the hardware would force a reset seconds later. But in these seconds, the input to the optics would not be sanitized! The module meant to do so would be shut down and the robot's eyes could accept her code by mistake. She could even prevent a local reset. Only a full clean restart triggered by the core watchdog of the robot could fix it. But that would happen a minute later. An eternity in combat!

 In other words, Mokoto could flash her code directly to the robot's protected memory via its optics! All she had to do was force an optical reboot several times in quick succession. The entirety of the robot could not be overwritten. The code architecture prevented a memory overflow from the optics to other components in the robot. Thus, there was a creativity limit to the mayhem Mokoto could cause. And yet! It was more than enough.

 There was a program that was small, fast, distracting, and could run on anything…Mokoto would overwrite the robot's optics with 1993 DOOM! The game had endured in one way or another over the decades. Every time it was lost, a netrunner would find an old copy on someone's fridge or cyberware. It was perfect!

 Mokoto would call her new Quickhack Doomguy. Sasha would love it. And she and Maine would stop treating Mokoto like a StreetKid!

* * *

Spoiler: Why create this Quickhack?

Reboot optics lasts a maximum of 16 seconds while this lasts a minute.

Spoiler

And because of DOOM!

Spoiler

But really, don't think too hard about it.

 Last edited: Nov 2, 2023
