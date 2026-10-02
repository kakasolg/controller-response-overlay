# Controller Response Overlay

A lightweight, **read-only** game controller overlay for Windows. It shows the buttons, triggers and sticks you are
pressing, plus one small status lamp. It never changes, blocks or injects controller input.

![full layout, demo input](docs/demo-full.jpg)

**Status: Phase 1 (MVP).** The overlay works as a controller viewer. The lamp only tells you whether controller data is
arriving: green means data is coming in, gray means none is. It does not judge input quality yet. See [DESIGN.md](DESIGN.md)
(Korean) for the full design, including the later phases.

## What it shows

- A, B, X and Y; LB and RB; Back and Start; the D-pad; L3 and R3 (the stick ring lights up)
- LT and RT as analog bars (0–255)
- Left and right stick direction and magnitude, raw. No deadzone is applied; the standard deadzone is drawn as a
  faint dashed ring for reference only.
- A status lamp: ● green means controller data is arriving, ○ gray means no data (no pad, unplugged, or no server).
  Each state has its own shape as well as its own colour.

## Run

Requires Windows and Python 3.12 or newer. It uses the standard library only.

```bash
python -m cro
```

Then open `http://127.0.0.1:47820/`, or add it as an **OBS Browser Source**; the background is transparent.

```bash
python -m cro --demo
```

`--demo` uses a fake pad, so you can preview the overlay on any OS with no controller. Every 30 s the fake pad
unplugs for 3 s, so you can see the gray lamp too.

Press **Ctrl+Shift+F10** to hide or show the overlay. The overlay reads this key combo by polling and never hooks the
keyboard, so the game still receives these keys too.

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

Example for OBS: `http://127.0.0.1:47820/?layout=streamer` with a 560×330 Browser Source.

## What it does not do

- It does not write to the controller: no vibration, no virtual controller, no remapping, no input injection.
- It installs no hooks, does no DLL injection, never touches the game process and never takes focus.
- It saves no files and keeps no logs. The server listens on `127.0.0.1` only and answers only local `Host` headers.
- It does not measure game latency, hardware polling rate, FPS, battery, cable condition or fatigue, and it does not
  claim to.
- It does not identify physical vs. virtual pads. XInput can't tell them apart: virtual-pad drivers, Steam Input and
  remappers all appear as an Xbox 360 pad. That's why the info line says `source unknown`.

The timestamps are when this overlay read the state, which is not when the controller sent it. Polling also misses states
that come and go between two reads; `debug=1` counts those from XInput packet-number gaps.

## Tests

The tests run offline and need no controller or game:

```bash
python -m pytest
```

`tests/test_readonly.py` scans the package source for anything that would write to a device, inject input, hook the
keyboard, touch another process, change focus or write files.

## Roadmap

1. **Phase 1 (this release):** read-only XInput viewer, web UI / OBS source, gray/green lamp.
2. **Phase 1b:** a standalone click-through, always-on-top window for players who don't stream.
3. **Phase 2:** a dual viewer for RAW (physical device) vs. OUTPUT (virtual pad) input. This first needs a prototype for
   device identification (Raw Input / HID / GameInput).
4. **Phase 3:** a lamp that compares input consistency to *your own* baseline (gray until there's enough baseline). It
   says nothing about causes and never changes input.

## 한국어 요약

게임을 하면서 지금 누르는 패드 버튼, 트리거, 스틱 방향과 세기를 보여 주는 **읽기 전용** overlay입니다. 입력을 바꾸거나
막거나 보내지 않습니다. Phase 1의 상태등은 "패드 데이터가 들어오는지"(초록 ●, 회색 ○)만 뜻하고, 반응 품질을
판정하지 않습니다. 설계 문서는 [DESIGN.md](DESIGN.md)에 있습니다.

## License

MIT
