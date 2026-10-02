# 설계 — Controller Response Overlay

게임 중 지금 누르는 패드 버튼·트리거·스틱 방향과 세기를 보여 주는 가벼운 **읽기 전용** overlay.
처음엔 스트리머용 controller viewer처럼 보이지만, 길게는 조작감 개선 모드의 optional add-on이 될 수 있다.
이 문서는 Phase 1 구현의 근거와 Phase 2·3 설계다. 수치 중 "임시"라고 적은 것은 정책이 아니라 데이터를 모은 뒤 정할 제안값이다.

출발점: [dsr-bot](https://github.com/kakasolg/dsr-bot)에서 쓰던 읽기 전용 XInput 관측(`radar_pad.py`, `observe_record.py`)과
투명 overlay 창(`overlay.py`). 이 저장소는 그 코드를 import하지 않는다 — 필요한 개념과 짧은 코드만 옮겼다.

---

## 0. UX 원칙

- 화면엔 Xbox식 패드 상태와 아주 작은 상태등 하나. 등은 **Gray / Green / Yellow / Red**만.
- 기본 화면엔 원인 설명·경고 문장·피로·케이블·배터리·프레임 드롭 진단을 **넣지 않는다**. 라벨은 기본 꺼짐, 켜면 "Response" 또는 "반응".
- 평소와 다를 때 색만 조용히 바뀌는 쪽을 우선한다. 세부 수치·기술적 이유는 opt-in debug 패널에만.

## 1. 프로젝트 경계

dsr-bot에서 **가져온 것** (개념·짧은 코드 복사, 같은 저자·MIT):

| 출처 | 가져온 것 | 바꾼 점 |
|---|---|---|
| `radar_pad.py` | XInput 구조체, DLL 순서(1_4→1_3→9_1_0) | `dwPacketNumber`를 남김, 빈 slot은 2 s마다만 |
| `observe_record.py` | 바뀔 때만, 원시 값, 연결/끊김 이벤트 | 기본 무기록 |
| `overlay.py` | 클릭 통과·포커스 안 가져가는 창 스타일 (Phase 1b) | |
| `radar.html drawPad()` | 그리는 방식 | slot 추측 제거 |

**가져오지 않은 것**: 가상 패드(vgamepad)·패드 잠금·봇 상태·게임 메모리 읽기/쓰기 전부, 그리고
`overlay.py`의 포커스 되돌리기(`keybd_event`로 Alt 합성 + `SetForegroundWindow` — 합성 입력이자 포커스 변경이라 불변식 위반),
`radar.html`의 "slot 1 우선" 휴리스틱(봇 가상 패드 자리를 가정한 추측).

별도 저장소로 둔 이유: import 경로가 물리적으로 없어 봇 코드가 섞일 수 없고, 일반 게이머에게 "가상 패드 없는 읽기 전용 도구"로
설명할 수 있고, 봇 저장소의 작업 규칙·P0 소스 스캔 범위와 얽히지 않는다. 대가는 XInput 코드 약 40줄의 중복.

## 2. Windows 입력 관측

| API | 읽기 전용 | 백그라운드 | 장치 식별 | 타이밍 | 메모 |
|---|---|---|---|---|---|
| **XInput** `XInputGetState` (Phase 1) | 예 | 됨 (작성자 녹화로 확인) | 공개 API엔 없음 | 폴링 시각뿐, `dwPacketNumber`는 상태가 바뀔 때만 증가 | 4 slot, LT/RT 분리. MS 문서: 빈 slot을 매 프레임 폴링하지 말 것 |
| XInput 비공개 서수 (#100 GetStateEx, #108 GetCapabilitiesEx) | 예 | 같음 | VID/PID | 같음 | 비공개 — 안정성 UNKNOWN |
| Raw Input (`RIDEV_INPUTSINK`) | 예 (공유) | 됨 | device path → VID/PID | report마다 (OS 처리 시각) | HID 패드만. Xbox 유선은 HID 호환 층에서 트리거 합쳐짐. report가 장치 주기로 계속 오는지 장치별 UNKNOWN |
| hidapi | `hid_read`만이면 예 | 됨 | 됨 | report 단위 | output/feature report 쓰기 금지 |
| DirectInput8 | NONEXCLUSIVE·BACKGROUND일 때만 | 됨 | 일부 | 폴링 | Xbox 패드 LT/RT 한 축 — 가치 낮음 |
| Windows.Gaming.Input | 예 | 데스크톱 앱 무포커스 시 UNKNOWN | VID/PID | Timestamp | |
| GameInput | 예 | focus policy에 따름, UNKNOWN | VID/PID | µs timestamp | C/C++ 전용 — Phase 3 후보 |
| SDL3 / pygame-ce | 조건부 | 힌트 필요 | 됨 | 이벤트 | HIDAPI 드라이버가 PS4/PS5/Switch에 output report(LED 등)를 보냄 → 끄지 않으면 읽기 전용 아님 |
| 브라우저 Gamepad API | 예 | OBS CEF에서 실무상 동작, 보장 UNKNOWN | XInput 패드는 VID/PID 없음 | timestamp | 설치 불필요 |

**범위.** XInput만(Phase 1): Xbox 360/One/Series·대부분의 XInput 패드 — 그리고 가상 패드(ViGEm 계열, Steam Input, 리매퍼)도
똑같이 보인다. DualSense·Switch Pro 원본은 안 보이고, 리매퍼를 거치면 그 출력이 보인다.
XInput + Raw Input/HID(Phase 2~): 장치 식별·report 단위 타이밍·비XInput 패드. 대가: HID 해석, 장치별 매핑, XInput slot ↔ HID 장치
대응(상태 비교 휴리스틱, 신뢰도 UNKNOWN).

**물리/가상 구분.**

| 경우 | XInput만 | + Raw Input/SetupAPI |
|---|---|---|
| 실제 Xbox 패드 | slot n, 출처 UNKNOWN | 부모 devnode가 USB/BTH → 아마 물리 |
| ViGEm 가상 패드 | 구분 불가 (기본 045E:028E = 실제 360 유선) | 부모가 ViGEmBus → 아마 가상 (prototype 확인 필요) |
| Steam Input 가상 패드 | 구분 불가 | UNKNOWN |
| 게임이 어느 slot을 읽나 | UNKNOWN | UNKNOWN |

Phase 1은 출처를 말하지 않는다 — `slot n · source unknown`. "Physical"·"RAW"라는 말을 쓰지 않는다.

**폴링의 한계 (작성자 녹화 1개, 2026-10-02, 명목 120 Hz 폴링, slot 0의 연속 관측 변화 7,174건).**
`dwPacketNumber` 증가폭이 1인 경우는 603건(8%)뿐 — 나머지는 2~6 이상 건너뜀. 관측 간격 p50 15.5 ms, p95 31.3, p99 171.8, 최대 5,975 ms.
1. overlay가 본 상태 변화 ≠ 실제 하드웨어 packet 도착. 중간 상태 대부분을 못 봤다.
2. p50 ≈ Windows 기본 timer tick(15.6 ms) — 간격을 정한 건 패드가 아니라 관측 루프였을 가능성이 크다 (추정).
3. 상태가 안 바뀌면 packet도 없다 → 사용자가 가만히 있는 것과 보고가 끊긴 것이 구분 안 됨 → **XInput만으로는 report gap을 못 잰다.**
4. 한계: 파일 1개, `dwPacketNumber` 증가 방식은 드라이버마다 UNKNOWN.

Phase 1 구현은 `debug=1`에서 이 건너뜀 수(`missed`)를 보여 줄 뿐, 판정에 쓰지 않는다.

## 3. Overlay 구현 후보

| | 단독 투명 창 | 로컬 웹 UI + OBS Browser Source | OBS plugin |
|---|---|---|---|
| 난이도 | 낮음 | 낮음 | 높음 (C/C++, OBS SDK) |
| 투명 배경 | colorkey layered (가장자리 한계) | 기본 | 됨 |
| 클릭 통과 | `WS_EX_TRANSPARENT` | 해당 없음 | 해당 없음 |
| GPU/CPU | CPU 합성, 바뀔 때만 그리면 작음 | OBS CEF(GPU) | 가장 작음 |
| 스트리머 | 화면 캡처 필요 | **가장 좋음** | 좋음 (설치) |
| 일반 게이머 | **가장 좋음** (전용 전체화면에선 가려짐) | 본인 화면엔 안 보임 | OBS 필요 |
| 장애 격리 | 별도 프로세스 | reader·렌더러 따로 죽음 | **OBS 안 — 죽으면 방송이 끊김** |

**구조 (Phase 1 구현):** reader 프로세스 하나(XInput 읽기 전용, `127.0.0.1` SSE) + 판단 없는 렌더러들.
렌더러는 웹 페이지 하나(OBS 소스 겸 브라우저), 단독 창은 Phase 1b. reader가 죽으면 렌더러는 1.5 s 뒤 Gray·중립 표시,
렌더러가 죽어도 reader는 그대로. OBS plugin은 MVP에 넣지 않는다 (input-overlay는 GPL-2.0 — 참고만).

**지연에 영향을 주지 않는 규칙:** SetState·독점 open·훅·DLL 주입·포커스 변경 없음. 빈 slot은 2 s마다. 120 Hz(임시) 폴링,
프로세스 우선순위 below-normal. 렌더러는 메시지가 올 때와 0.25 s마다만 그리고, 페이지가 안 보이면 그리지 않는다.

## 4. UI

```
 [LT ▮▮▯]  (LB)                    (RB)  [RT ▮▯▯]   ●  ← 상태등 (오른쪽 위)
      ╭─L─╮       ▭  ▭              (Y)
      │ ● │                      (X)   (B)
      ╰───╯                         (A)
           ✚ D-pad        ╭─R─╮
                          │ ●╲│
                          ╰───╯
```

- **full** 360×210, **compact** 200×72 (Back/Start·글자 라벨 생략), **streamer** = full + 외곽 그림자 + 1.5배.
- **스틱**: 원(게이트) 안 점 + 중심에서 선, ±32767 원시 값 그대로 (원형 클램프·deadzone 적용 없음). 표준 deadzone은 옅은 점선 고리로 참고만. L3/R3는 게이트 테두리 강조.
- **트리거**: 0–255 세로 막대. **버튼**: 눌리면 흰색으로 채움 — 초록·노랑·빨강은 상태등 전용으로 남겨 둔다.
- **짧은 누름**: 한 프레임보다 짧은 누름도 다음 프레임에 한 번은 보인다 (단, 100 ms 안에 그릴 프레임이 있을 때만 — 숨은 페이지에서 쌓이지 않게).
- **상태등**: 오른쪽 위, full 10 px / compact 7 px, 어두운 1 px 외곽선. 깜빡임·페이드 없음.
- **라벨**: 기본 꺼짐. "Response"는 영어권·방송에 맞지만 "응답 속도를 쟀다"로 읽히기 쉽고, "반응"도 같은 오해 + 다국어 문제. 켤 땐 hover/상세에서만 "개인 기준 대비 상대적 일관성, 속도 측정 아님"을 밝힌다. Phase 1 등은 데이터 유무만 뜻하므로 라벨 자체가 이르다.
- **접근성**: 색 + 모양. Gray ○ 빈 고리 · Green ● 원 · Yellow ◆ 마름모 · Red ■ 사각형. 색은 Okabe-Ito (#9a9a9a, #009e73, #f0e442, #d55e00).
- **보이기 단축키**: Ctrl+Shift+F10, `GetAsyncKeyState` 폴링 (입력을 소비하지 않음, 훅 없음). `RegisterHotKey`는 게임에서 그 조합을 뺏고, 패드 조합은 게임에도 들어가서 쓰지 않는다.

## 5. 상태등

### Phase 1 (구현됨 — 판단 없음)

| 색 | 조건 |
|---|---|
| Gray ○ | 서버 없음/1.5 s 넘게 메시지 없음 · 선택 slot에 패드 없음 · reader가 1 s 넘게 그 slot을 못 읽음 |
| Green ● | 선택 slot의 데이터가 들어오고 있음 — "좋음"도 "빠름"도 아니다 |
| Yellow/Red | 쓰지 않음 (모양만 정의됨) |

### Phase 3 (설계) — 개인 baseline 대비 상대적 일관성

이 등은 원인 진단도 health 진단도 아니다. 게임 메모리·화면을 안 보므로 **게임 반응은 원리적으로 못 잰다** — 볼 수 있는 건 입력 경로의 일관성뿐.

| 신호 | 필요한 API | 이상 방향 |
|---|---|---|
| report 간격 median, p95/p99 | Raw Input/GameInput (XInput 불가, §2) | 증가 |
| jitter (간격의 MAD/IQR) | 같음 | 증가 |
| gap 빈도 (기준 p99의 k배 초과/분) | 같음 | 증가 |
| 재연결 수 | XInput 가능 | 증가 |
| 중립 스틱 드리프트 (버튼 없음·2 s 이상 정지 구간의 정지 위치 중앙값과 퍼짐) | XInput 가능 | 증가 |
| overlay 자기 점검 (자기 루프 지각) | 내부 | 늦은 구간은 "증거 없음" — Yellow로 만들지 않음 |

- **단측 판정**: 기준보다 빠르거나 낮은 건 이상이 아니다. "평균 이하"가 아니라 지연 증가·변동성 증가·gap 증가만 본다. 평균 하나로 판단하지 않는다.
- **baseline**: 프로필 키 = 장치 경로 해시 + 연결 방식 + API + baseline_version. 부족하면 Gray (임시: 3세션·활동 20분). Green 구간만 천천히 반영해 이상 구간이 기준을 오염시키지 않게.
- **hysteresis (전부 임시 제안값)**: 10 s 창마다 신호별 수준 0/1/2 (예: 현재 p95 / 기준 p95가 1.5배면 1, 2.5배면 2).
  Green→Yellow: 최근 4창 중 3창 ≥1. Yellow→Red: 4창 중 3창 =2 그리고 Yellow 30 s 이상 — Green에서 바로 Red로 가지 않는다.
  회복: 60 s 깨끗하면 한 단계 — 오를 때보다 천천히. 활동 부족·자기 점검 지각 창은 어느 쪽으로도 안 센다 (많으면 Gray). 끊김은 Red가 아니라 즉시 Gray.
- 원인 후보(케이블, Bluetooth, 배터리, 장치 노화, 게임 hitch, PC 부하, 피로)는 내부에도 확정·저장하지 않는다. debug 패널도 "간격 퍼짐이 기준보다 큼"처럼 현상만.
- Yellow/Red여도 어떤 입력도 막거나 바꾸지 않는다.

## 6. Phase 2 (설계) — RAW / OUTPUT 이중 표시

- **RAW**: 장치 경로로 식별된 물리 장치를 Raw Input/HID로 읽은 값. 식별이 확정될 때만 이 이름표.
- **OUTPUT**: 가상 패드의 보고를 XInput slot에서 다시 읽은 값 (나중엔 매퍼가 로컬 채널로 스스로 알림).
- **PASS-THROUGH**: 매퍼가 "그대로 넘긴다"고 주장하는 상태 — 주장으로만 표시하고, RAW와 OUTPUT의 일치 여부를 따로 보인다.
- 두 패널은 머리글·테두리(RAW 실선, OUTPUT 점선)·출처 라벨로 구분. 출처가 UNKNOWN이면 그 패널은 "?" — 자동으로 RAW/OUTPUT에 배정하지 않는다.
- **double input**: 매퍼가 가상 패드를 만들고 물리 패드를 숨기지 않으면 게임은 둘 다 본다. overlay는 "게임에 보일 수 있는 패드 N개"만 보이고, 게임이 실제로 무엇을 읽는지는 UNKNOWN.
- **소유권**: 물리 장치는 OS 공유, 가상 장치는 만든 프로세스 소유. 장치 숨기기(HidHide 등)는 이 프로젝트 밖. overlay는 소유권을 바꾸지 않고 표시만.
- 같은 물리 장치가 XInput·Raw Input 양쪽에 보이면 대응시켜 한 패널로. 대응이 불확실하면 둘 다 그리고 "같은 장치일 수 있음" — 자동 병합 안 함.
- 시작 조건: 장치 식별 prototype (Raw Input 장치 경로 + devnode 부모 버스, GameInput 비교).

## 7. 로그·개인정보

- **Phase 1은 아무 파일도 쓰지 않는다** (소스 스캔 테스트로 확인).
- Phase 3에서 켜면 세션 요약만:

```json
{"schema":"cro-summary/1","session_start":"2026-10-02T13:26","dur_s":1800,
 "profile":{"dev_hash":"sha256(salt+path)","conn":"usb|bt|unknown","api":"xinput"},
 "baseline_version":3,"connected_s":1790,"reconnects":0,
 "gap_ms":{"p50":8.0,"p95":9.1,"p99":12.0},"jitter_ms_mad":0.4,"gap_events":2,
 "neutral_drift":{"l":[31,111],"r":[0,0]},
 "transitions":[{"t_s":620,"from":"green","to":"yellow"}]}
```

- 장치 경로엔 BT MAC·시리얼이 들어갈 수 있다 → salt 넣은 해시만.
- 원시 입력 전체 기록은 debug opt-in에서만: 명시 플래그, 화면에 REC 표시, 자동 종료(임시 10분), 로컬만, 삭제 명령. 기록기는 호출 쪽을 막지 않는 큐 + 오류 시 스스로 꺼짐.
- 수집하지 않음: 게임 계정, 채팅, 화면 캡처, 게임 메모리, 키보드·마우스 입력(단축키 조합 확인 제외), 이동 경로, 창 제목, 외부 전송. 서버는 `127.0.0.1`만.

## 8. 안전 불변식

1. Phase 1 overlay는 controller input을 수정하지 않는다 — `XInputGetState`만 바인딩 (`tests/test_readonly.py`).
2. overlay가 죽거나 멈춰도 게임 입력은 막히지 않는다 — 별도 프로세스, 훅·주입·독점 open·포커스 변경 없음.
3. 패드 끊김은 overlay 상태(Gray)만 바꾼다 — 재연결 시도·장치 조작 없음.
4. 가상 패드·매퍼 기능이 없는 동안 gamepad 소유권을 바꾸지 않는다 — 장치를 만들지도 숨기지도 독점하지도 않는다.
5. RAW와 (미래의) OUTPUT을 섞어 표시하지 않는다 — 식별 전엔 `slot n · source unknown`.
6. 게임 지연·하드웨어 polling rate·피로·케이블·FPS를 쟀다고 말하지 않는다. 타임스탬프는 overlay가 읽은 시각.
7. 포커스를 바꾸지 않고, 합성 키 입력을 만들지 않는다.

## 9. 성공 기준

| Phase | 기준 | 확인 |
|---|---|---|
| 1 | 입력이 보임 | `--demo`와 실제 패드로 모든 버튼, LT/RT 0–255, 스틱 4방향·대각 |
| 1 | 끊김·재연결 | 케이블 뽑으면 다음 폴링에서 Gray, 꽂으면 ≤2 s(빈 slot 재확인 주기) 안 Green — demo는 30 s마다 3 s 끊김으로 재현 |
| 1 | 지연 무영향 | **직접 측정 불가(UNKNOWN)** — 간섭 경로 없음(소스 스캔) + overlay CPU 예산(임시 <1% 코어) |
| 1 | 장애 격리 | reader/렌더러 강제 종료해도 패드 입력 그대로 (다른 XInput 뷰어로 확인) |
| 2 | 이중 표시 정확성 | 테스트용 가상 패드 + 물리 패드에서 RAW/OUTPUT 혼동 없음, 불확실하면 UNKNOWN |
| 2 | double input 없는 표시 | 같은 장치가 두 번 그려지지 않음 (또는 "같은 장치일 수 있음") |
| 2 | 소유권 표시 | 가상 장치 소유 프로세스·게임에 보일 수 있는 패드 수 |
| 3 | baseline 부족 → Gray | 새 프로필은 Gray 유지 |
| 3 | 상대 판정만 | 기준보다 좋은 값은 Yellow가 안 됨 |
| 3 | 오탐 억제 | 순간 spike를 넣은 재생 데이터에서 색 안 바뀜 |
| 3 | 원인 단정 없음 | UI·저장 파일 어디에도 원인 단어 없음 |

## 10. 남은 UNKNOWN

- Steam Input이 켜져 있으면 XInput에 보이는 건 Steam의 가상 출력 — 표시는 되지만 RAW가 아니다.
- 게임이 어느 slot을 읽는지. 다른 가상 패드가 같이 켜져 있으면 slot이 2개 → `slot=` 옵션으로 고르고 추측하지 않는다.
- 전용 전체화면에선 단독 창(Phase 1b)이 가려진다.
- OBS Browser Source에서 장시간 동작·CPU 사용은 아직 측정 안 함.
