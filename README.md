# Controller Response Overlay

A lightweight, **read-only** XInput controller viewer for Windows. It shows the buttons, triggers and sticks that
XInput reports for one slot, plus one small status lamp. It only reads XInput state; it does not write to, remap or
inject controller input.

![full layout, demo input](docs/demo-full.jpg)

**Status: Phase 1 (MVP).** Manually verified in one environment only — see [Verified so far](#verified-so-far). Everything
outside that list is untested. See [DESIGN.md](DESIGN.md) (Korean) for the design, including later phases that are
**not implemented**.

## What it shows

- A, B, X and Y; LB and RB; Back and Start; the D-pad; L3 and R3 (the stick ring lights up)
- LT and RT as analog bars (0–255)
- Left and right stick direction and magnitude, raw. No deadzone is applied; the standard deadzone is drawn as a
  faint dashed ring for reference only.
- A status lamp that is a **data-availability signal only**:
  - ● green: the reader is reading the selected XInput slot and the page is receiving it
  - ○ gray: no state for the selected slot — nothing connected there, disconnected, or the reader/server stale or gone

  The lamp says nothing about response speed, latency, input quality or controller health. Each state has its own
  shape as well as its own colour.

## Run

Requires Windows and Python 3.12 or newer (verified only with 3.12.10). It uses the standard library only.

```bash
python -m cro
```

Then open `http://127.0.0.1:47820/` in a browser. Pick the slot explicitly with `?slot=N`; `http://127.0.0.1:47820/state`
lists which slots currently have state.

```bash
python -m cro --demo
```

`--demo` uses a fake pad on slot 0, so you can preview the overlay with no controller. Every 30 s the fake pad unplugs
for 3 s, so you can see the gray lamp too. (Only tried on Windows.)

**OBS Browser Source — untested.** The page has a transparent background and is meant to be usable as an OBS Browser
Source (for example `http://127.0.0.1:47820/?layout=streamer` at roughly 560×330), but this has not been tried yet.

**Hide/show hotkey — implemented, not manually verified.** The reader polls Ctrl+Shift+F10 (no keyboard hook) and toggles
visibility on every open page. It has only been checked by an offline unit test, not on real hardware.

### Page options (query string)

| option | values | default |
|---|---|---|
| `layout` | `full`, `compact`, `streamer` (full + outline, 1.5×) | `full` |
| `slot` | `auto` (lowest connected XInput slot), `0`–`3` | `auto` |
| `scale` | 0.25–6 | 1 (streamer 1.5) |
| `label` | off, `response`, `ko` (반응) | off |
| `info` | `1` shows `slot n · source unknown` | off |
| `debug` | `1` shows raw values, packet number, missed changes | off |
| `bg` | transparent, `dark`, `light` | transparent |

## Verified so far

One manual run on commit `9b516b0`. In this environment:

| | |
|---|---|
| OS / Python | Windows 10.0.26200, Python 3.12.10 |
| Controller | one Xbox Series controller, Bluetooth, XInput slot 0 |
| Other software | Steam running with Steam Input **off** for this controller; no remapper, virtual controller, game or OBS running |
| Browser | the Claude desktop app's built-in browser pane (Chromium-based) |

- [x] Offline tests: 23 passed
- [x] Demo mode: full / compact / streamer layouts, fake unplug → gray → green, reload, server stop → gray
- [x] Buttons: A, B, X, Y, LB, RB, View (Back), Menu (Start), L3, R3 — each shown as the button pressed
- [x] D-pad: up, down, left, right, and up+right together
- [x] Triggers: LT and RT reach 255, with intermediate values shown
- [x] Sticks: both sticks show the correct direction for up / down / left / right
- [x] In a recorded session of 4,993 rendered frames, the drawn buttons never differed from the raw state for 3+ frames
- [x] Compact and streamer layouts with the real controller
- [x] Controller off → gray; on again → green on the same slot
- [x] Empty slot selected (`slot=3`) → gray, `no controller`
- [x] Reader stopped → page gray with neutral inputs (≈1.6 s); reader restarted → page reconnects (≈1.8 s)
- [x] Browser tab closed → reader keeps running; reader stopped → Windows (`joy.cpl`) still sees the controller
- [x] Window minimized and restored → no phantom buttons on return

Not verified (treat as unknown):

- OBS Browser Source; any other browser; the hide/show hotkey on real hardware
- Other controllers; wired or wireless-dongle connections; more than one controller or XInput slot
- Steam Input on; remappers or virtual controllers running alongside
- Full ±32767 on every stick direction (only "up" reached the edge in the test)
- Whether drawing actually pauses while the window is minimized
- Long-running CPU and memory use
- Any effect, or lack of effect, on a game's input — no game was run

## Limitations and what it does not do

- **It cannot tell where a slot's state comes from.** XInput gives no device identity: a physical pad, Steam Input,
  a remapper or a virtual controller all look the same. The overlay does not identify a physical controller, raw input
  or game output, which is why the info line says `source unknown`. `slot=auto` just picks the lowest slot number.
- It does not write to the controller: no vibration, no virtual controller, no remapping, no input injection.
- It installs no hooks, does no DLL injection and does not access other processes (checked by a source scan in the tests).
- It saves no files and keeps no logs. The server listens on `127.0.0.1` only and answers only local `Host` headers.
- It does not measure or claim anything about input latency, game latency, hardware polling rate, FPS, battery, cable
  condition, controller health or fatigue, and makes no claim about performance impact on games.
- Times are when this overlay read the state, not when the controller sent it. Polling also misses states that come and
  go between two reads; `debug=1` counts those from XInput packet-number gaps.

## Tests

The tests run offline and need no controller or game:

```bash
python -m pytest
```

`tests/test_readonly.py` scans the package source for anything that would write to a device, inject input, hook the
keyboard, touch another process, change focus or write files.

## Roadmap

Only Phase 1 exists. Everything below it is design, not implemented or verified.

1. **Phase 1 (this release):** read-only XInput slot viewer, browser page, gray/green data-availability lamp.
2. **Phase 1b (not implemented):** a standalone click-through, always-on-top window for players who don't stream.
3. **Phase 2 (not implemented):** a dual viewer for RAW (physical device) vs. OUTPUT (virtual pad). It first needs a
   prototype for device identification (Raw Input / HID / GameInput).
4. **Phase 3 (not implemented):** yellow/red that compare input consistency to *your own* baseline (gray until there's
   enough baseline). It would say nothing about causes and never change input.

## 한국어 요약

XInput이 보고하는 패드 상태(버튼, 트리거, 스틱 방향과 세기)를 한 slot씩 보여 주는 **읽기 전용** viewer입니다. XInput 상태를
읽기만 하고, 패드에 쓰거나 입력을 바꾸거나 보내지 않습니다. 상태등은 **데이터가 들어오는지**만 뜻합니다(초록 ●: 선택 slot을
읽고 있음, 회색 ○: 그 slot에 상태가 없거나 끊겼거나 reader가 멈춤). 반응 속도, 지연, 패드 상태를 판정하지 않고,
그 slot이 물리 패드인지, 원시 입력인지, 게임에 들어가는 출력인지도 구분하지 못합니다.

실제 검증은 Windows 10.0.26200 · Python 3.12.10 · Xbox Series 패드(Bluetooth, slot 0) · Steam Input 꺼짐 · 앱 내장
브라우저 한 환경뿐입니다. OBS, 단축키, 다른 패드·연결 방식·브라우저, Steam Input·리매퍼 공존, 게임에 미치는 영향은
검증하지 않았습니다. 설계 문서는 [DESIGN.md](DESIGN.md)에 있습니다(Phase 2·3은 설계만 있음).

## License

MIT
