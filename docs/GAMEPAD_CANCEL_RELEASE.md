# B / Start release cancellation on controller loss (2026-10-14)

## Verified native event chain
Supported MCAlpha.dll SHA256: 5c701de93af6267b959c49e6927bee525bc0f3c68c8c6f51413515d13809d427.
RVA 557ee dispatches right button counter 2 == -1 to vtable +1a4. Base implementation 564cd forwards event 40; first press 56482 forwards 3f.
World GUI 80932 forwards 40 to its listener. World handler 6e6d8 accepts sender ID42 only when world GUI +190==1, stops mouse movement then requests field mode5 via 6e246. Handler 6e499 writes +156c=5. This is a mode request, not proof the menu was displayed.
REA evidence:
- ev_494e0e8369a4ac0fc21e56f21356a7e72a4d0eddc52080907381007e6d0b7799 (mouse dispatch)
- ev_e7b65852af0c29739c9d3ce092f89044676bb4fd190787e5ad9fbf79813afe37 (right release)
- ev_d8c5b0c9a27d62d8dd74c96c5e6d28fbcedb5d4914fd439e129375a37cc208f5 (right press)
- ev_43ecbfa9fda80877c6a4ee9419e8a9b2f839736e30fdafc3d84d3735dee55183 (world GUI)
- ev_078c19477170d8be1e072f40c4ad26c458307637d2fc1dacf81e0e414a0cfacf (world listener)
- ev_30e573bbd8b409e40b9b36a394d135e3cbf1e68a1ad26426358cdec42661a6cd (mode request)
- ev_a3633b884e931fa56ed113fc138dc3612f33065dd9c340904161fa5923fb0ad1 (mode5 write)

## Observed controlled failure and repair
New replay with previous production hooks failed:
`FAIL disconnect while B held must cancel right release instead of returning menu` (exit1).
The right-button native counter converted the disappearing synthetic press to release. Previous cancellation handled only A/X left presses.
Track syntheticRightOwned using raw physicalRight before key merging; controller disconnection/replacement clears only that owned right counter at f1c9c + VK_RBUTTON*4. Both owned mouse presses share the sampled controller identity. Removal resets both ownership flags. Normal connected B/Start release stays native; physical mouse priority and neutral rearm remain intact. Right base callbacks do not use the left pressed visual helper. Focus-loss path remains unchanged (Alt+Tab deferred).

## Coverage
Owned production input/UI hooks + source-shaped counters/right-release callback: B press/intentional release; held disconnect/reconnect; slot replacement; physical right hold/release overlapping disconnection; exploration Start release requests5 only once; disconnection cannot request5.
Menu replay82 checks (baseline71), full world92 (baseline81). IAT passthrough/rollback fixture passes; Python456 passes. Isolated modified replay82, two-file restored rebuild71.
No commercial DLL code, menu rendering, task execution, saved-game loading or physical Xbox was executed. In-menu callback proves the right-release event, not every actual menu's return action. Actual game acceptance remains pending.

## Runtime / manual acceptance
Only input-diagnostics.dll updated; accepted motion-space/display/camera/maps hashes unchanged. Shared runtime/data, no full game copies, defaults untouched.
Continue runtime/Play-gamepad.cmd: opening A skip, D-pad/left stick selection, A press/release confirmation, B return; exploration Start press/release opens menu. Verify real mouse and keyboard takeover.
Optional: hold B on a harmless submenu or hold Start while stationary, disconnect, reconnect; no unintended transition should occur. Neutral input then fresh deliberate press/release works.
After standalone Xbox passes, repeat runtime/Play-motion-gamepad.cmd. Do not mark all game states complete based on this fixture.
