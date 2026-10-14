# Xbox menu confirmation: disconnect cancellation

## Verified source contract
Supported MCAlpha.dll SHA256: 5c701de93af6267b959c49e6927bee525bc0f3c68c8c6f51413515d13809d427.
Title listener RVA b7ceb acts on event 3c (release), not event 3b (press).
If a controller disappears with its synthetic left mouse button held, the original input counter can produce a release and activate a title item unintentionally.
The owned input/UI/title-chain replay failed this assertion before correction.

## Correction
Track syntheticLeftOwned and syntheticLeftDevice separately from raw physical mouse state.
On controller disconnection or device replacement, zero only the owned left-button counter at f1c9c + VK_LBUTTON * 4; cancelMenuPress requests visual cleanup during GUI dispatch.
For exact native base buttons (vtable bee80, pressed flag +19c), invoke native visual clear helper 5718f. Its first seven bytes must be 55 8b ec 51 89 4d fc. This helper clears press state without calling the release listener.
Bounded tree traversal rejects unreadable pointers and cycles. Unknown derived layouts are not mutated.
Physical mouse release remains native. Neutral input rearms a reconnected/replacement controller. Normal connected A press/release still confirms. Focus-loss behavior is unchanged; Alt+Tab is deferred.

REA evidence: ev_d3284e2a96ca8bdfe5aac6e9f0760083789cd162d2ed7402c9b859cb50aac14c (visual helper).

## Controlled validation
world_gamepad_fixture --menu-dispatch-only: 71 checks, including synthetic cancellation, replacement device, physical overlap, neutral rearm, release-only title listener and press visual cleanup.
Independent original source rollback: 59 checks. Full Python suite: 456 tests.
These owned fixtures execute production hooks but source-shaped owned UI callbacks; commercial transition executor is not run. Actual Xbox menu behavior still requires player acceptance.

## Delivery and acceptance
Only runtime/modules/input-diagnostics.dll changes. Accepted motion-space/display/camera/maps modules stay unchanged. One runtime/data directory is reused.
1. Run runtime/Play-gamepad.cmd. Press and release A to skip the opening, then move through title items with D-pad/left stick.
2. Choose load (or another harmless submenu), press and release A; B returns. Verify pointer does not jump during navigation.
3. In-game, Start opens menu; D-pad/left stick changes selection, A confirms, B returns.
4. Optional: hold A on a harmless menu item, disconnect controller, then reconnect held. No option should activate; release to neutral, then fresh A press/release confirms.
5. After standalone input passes, repeat with runtime/Play-motion-gamepad.cmd.
Game was not launched by automation.
