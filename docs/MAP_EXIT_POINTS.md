# Per-Field candidate exit markers

## Verified native data contract

This feature derives candidate exit markers from Field regions and event scripts;
it does not infer doors from black textures, WRD triangles, or a global height cut.
The supported engine digests are shared with `resource_field.ENGINE_SHA256S`.
The current analyzed image is
`7e8649425217d3b99d52d11c679761a88c57b125c241b331aea5c25e00e3b15e`.

| Native RVA | Verified interpretation |
|---|---|
| `65f90`, called from `68996` | Writes the numeric Field ID at the start of the embedded FieldInfo at scene `+10cc`; the next DWORD, scene `+10d0`, is the WRD map ID. `+10cc` is not a FieldInfo pointer. |
| `6e5c7` | Looks up region ID in scene `+1528`, count `+1524`, stride `0xe8`. |
| `65f90` region reader | Serialized 112-byte region: center XYZ at `+0`, signed ID at `+12`, eight XYZ corners at `+16`. Runtime region ID is at `+0`, center at `+4`, and six planes start at `+70`, stride `0x14`. |
| `71af6 → 727e6` | Condition 304 reads actor selector and region ID. Selector `10000+n` requests actor ID `n`; actor position plus its body-height vector must lie on/inside all six region planes. |
| `6f14c` | Iterates scene actor pointers at `+155c`, count `+1560`, and compares each actor's `+328` identity. `10000` is not an alias for whichever actor is currently controlled. |
| `71b9b → 729b9` | Action 4 takes its first parameter as the destination Field and requests kind 31 through `c9fd`. |
| `71b9b → 72a76` | Action 5 also uses parameter 0 as destination Field; parameters 1 and 2 become destination entry-marker state, not destination map IDs. |

REA evidence identifiers:

- Dispatcher: `ev_e28726bb56ca4eb1043f1f8804dd480bc2d7361c32533d362e0e9ce379769abf`.
- Action 5: `ev_5595066558c848ce3ebb8b7a82d4c8d427965c65bbe09bfc827187c03797dbfb`.
- Condition 304 and action 4: `ev_76bcb27bd12881807b3ad7a96eddd5e2edad9639fc1fd9a3d039b161cdf9eca9`.
- Actor lookup and Field loader: `ev_bed27cea2f49d244df6485fe3c4c2d3af5b2a987df9ebfa908c40f11c598ed08`.

The local ignored maintenance directory preserves `map-exit-pseudocode.json`
and `map-exit-rea-evidence.json`. Decompilation is evidence, not original source.

## Extraction policy and remaining uncertainty

`build_map_points.py` requires a supported source engine, a fully parsed static
prefix, and an exact-EOF event tail. It accepts exactly one condition 304 in an
event, selector `10000..19999`, an existing nonnegative region ID, and action 4
or 5 with destination Field `0..9999`. Multiple region conditions are skipped
rather than guessing the logical relationship. Unknown commands are preserved
by the structural parser but not interpreted as exit markers.

Each row preserves the trigger actor ID. Rendering additionally matches that ID
to the current player at actor `+328`; an NPC's region trigger does not become a
player exit just because it shares a Field. Field and WRD map IDs must both match.
A shared WRD therefore cannot leak one story Field's exits into another Field.

The marker is the serialized region center projected on the atlas XY axes, not
an inferred doorway edge or navigable floor. The manifest retains the corners'
axis-aligned bounds for audit. Other conditions and finite event repeat limits
are not evaluated. Multiple transition actions produce separate audited rows,
not a guessed unique destination. A nonzero flags value renders a hollow marker;
no marker certifies current passability, reachability, collision, or story state.

202 movement and 700 dialogue alone are not transitions. In the current sources:

- Field 0751 / WRD 13 has actor-1 candidate exits in regions 0, 1, 3 to Fields
  0750, 0754, 0757.
- Field 0757 / WRD 17 has an actor-0 candidate exit in region 0 to Field 0751.
  Its region-1 stairwell return/dialogue event is deliberately not an exit.

## Rebuild and validation

```powershell
python tools/build_map_points.py --source runtime/data/Field --engine runtime/data/MCAlpha.dll --output runtime/maintenance/NEW-atlas/points
python -m unittest discover -s tests -p 'test_map_points*.py'
$env:PYTHONPATH='runtime/dependencies'
python tools/replay_native_map_points.py --engine runtime/data/MCAlpha.dll --report build/NEW-map-points-native.json
```

The output must be new and outside source resources. Only the new `points`
subdirectory is written; atlas PNG, MCM1 and atlas manifest files are unchanged.
The builder verifies engine and all Field hashes again before writing and before
publishing the manifest. Failed source versions are not silently accepted.

The 2026-10-25 source set has 597 Fields: 565 fully parsed and 32 rejected by
the supported structural reader, not declared corrupt. The accepted set produces
379 candidate markers. All 565 accepted Fields get a file, including zero-marker
files; 25 accepted Fields have map ID -1 and cannot match displayed terrain.
Rejected Fields have no POI file. These assets and source resources remain ignored.

The native replay executes condition 304, actor-ID lookup, six-plane tests, and
the action-4/action-5 parameter routes in the supported image. Six owned actor/
region cases and two transition cases pass. Scene cleanup and allocation are
explicit boundaries, and the transition executor is stopped before invocation.
No game, DLL entry point, live scene loader or renderer runs. This is not a claim
of actual in-game exit or fullscreen-map acceptance.

## MCP1 format

All fields are little-endian. The header is 16 bytes, `<4sIII>`:

`MCP1`, `field_id`, `map_id`, `count`.

`map_id == 0xffffffff` represents -1, a Field without map terrain. Count is at
most 64, and the file length must equal exactly `16 + count * 36`.
Each 36-byte row uses `<iiiiiIfff>`:

`event_index, region_id, target_field, target_map, trigger_actor, flags, x, y, z`.

- `target_map == -1`: destination map unknown or absent.
- `trigger_actor`: actor identity `0..9999`, not an NPC array index.
- flags bit 0: additional unevaluated conditions or multiple transition actions.
- flags bit 1: finite event execution limit; current execution count unknown.
- All other flag bits are rejected. XYZ must be finite.

`points/manifest.json` uses schema 1 and records `format`, `header_bytes`,
`row_bytes`, `source_engine_sha256`, `marker_count`, `accepted` and `rejected`.
Accepted entries contain `field_id`, source basename `file`, `source_sha256`,
`map_id`, `poi_sha256`, `points`, and `skipped_events`. Marker dictionaries include
all binary fields plus action/condition offsets, opcode, action index and region
bounds. Rejected entries contain the identity, source hash and reason. No personal
absolute source path is persisted. This manifest is consumed by deployment source
validation; it is not a replacement for runtime binary validation.
