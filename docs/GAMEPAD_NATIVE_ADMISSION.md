# Native mouse admission and offline title replay (2026-10-15)

## Verified
Supported MCAlpha.dll SHA256: 5c701de93af6267b959c49e6927bee525bc0f3c68c8c6f51413515d13809d427.
RVA 5663f admits visible (+e8), enabled (+160) widgets. Without an exclusive window, +164 must be 0 or 1. With one, 08f6a admits only the exact object returned by 021db from list head (manager+3c), not ordinary descendants. All 21 supported GUI vtable +1dc slots point to 5663f. Installation now guards those slots before writes. Child-first traversal remains unchanged.

The old focus collector omitted mode and exclusive-owner checks; the new regression failed against the old source and passes with the fix. Virtual selection must not point at controls rejected by native mouse admission.

## Original instruction replay
`tools/replay_native_title.py` hashes the local user-supplied image before mapping PE32 sections into Unicorn simulated memory. It never loads a game DLL or calls its entry point. Original 557ee mouse dispatch, hit testing, forwarding and b7ceb title listener execute in the emulator. The only owned ABI shim replaces imported _ftol in simulated RAM; it truncates x87 ST0 to EDX:EAX and restores the control word.

33 cases cover press/hold/release/idle, four title IDs, phase gating, visible/enabled/mode rejection, exclusive ownership, inclusive edges, fractional offsets and disabled-child traversal. Load/continue/exit release requests are 7/9/11, recorded at b874a without executing transitions. Start stops at allocation b8b5a (size 13c) before request 6; its transition is NOT validated. Instruction, time, executable-address, stack and FS exception-chain guards bound execution. Source image is reread unchanged; report aliases to the sample are rejected, including hardlinks. Checks remain enabled under python -O.

REA evidence: admission ev_00d6e1e610ec63db3abe410b217d22e72a78967cdce04f4c5724b13fc9cbdeb4; exclusive ev_24aa43181d3677e5252a317abcaeb58fdd5cda7af407b0d5237aa1bd203151ae; list head ev_c667bb4c1cfcb3a6b3f1043b6f3e2b4d459b8535abf3c1e132230e0a5ef67520; title listener ev_6afc626504fcaaf42f1d6e232f3a9d73a9ac08e2feb1b5d0818b8f35acea4a20.

## Boundaries and manual acceptance
The contract mismatch is verified; whether it caused the player's missing focus indication is unverified. Emulation proves neither rendered pointer visibility nor physical Xbox behavior nor resource loading. Menu native pointer visibility from GAMEPAD_MENU_LOCATOR.md is preserved; exploration cursor ownership, one-owner direction dispatch, X/Space mapping, accepted motion/camera/display and shared data are unchanged.

Use runtime/Play-gamepad.cmd manually: move through main menu and status/sidebar, observe the native pointer, release direction then press/release A. The selected item must match the pointer; green arrows must not move together with the sidebar. B returns; X interacts in exploration. Also check mouse takeover. No commercial game was started for this work.
