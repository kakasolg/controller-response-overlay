# 설계 — Controller Response Overlay

게임 중 지금 누르는 패드 버튼·트리거·스틱 방향과 세기를 보여 주는 가벼운 **읽기 전용** overlay.
처음엔 스트리머용 controller viewer처럼 보이지만, 길게는 조작감 개선 모드의 optional add-on이 될 수 있다.
이 문서는 Phase 1 구현의 근거와 Phase 2·3 설계다. 수치 중 "임시"라고 적은 것은 정책이 아니라 데이터를 모은 뒤 정할 제안값이다.

> **현재 상태**: 구현되고 수동 검증된 것은 Phase 1(XInput slot 상태 viewer, Gray/Green 등)뿐이고, 검증 범위는 §11의 한 환경이다.
> Phase 1b·2·3(단독 창, RAW/OUTPUT, Yellow/Red·baseline)은 **설계만 있고 구현·검증되지 않았다**.

출발점: [dsr-bot](https://github.com/kakasolg/dsr-bot)에서 쓰던 읽기 전용 XInput 관측(`radar_pad.py`, `observe_record.py`)과
투명 overlay 창(`overlay.py`). 이 저장소는 그 코드를 import하지 않는다 — 필요한 개념과 짧은 코드만 옮겼다.

---

## 0. UX 원칙

- 화면엔 Xbox식 패드 상태와 아주 작은 상태등 하나. 등은 **Gray / Green / Yellow / Red**만. 지금 구현된 건 Gray/Green뿐이고 Yellow/Red는 Phase 3 설계(§5).
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
| GameInput | 예 | focus policy에 따름, UNKNOWN | VID/PID | µs timestamp | C/C++ 전용 — Phase 3 후보 (Design only) |
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
렌더러는 웹 페이지 하나(브라우저 · OBS 32.2.2 Browser Source에서 확인, §11.5), 단독 창은 Phase 1b(미구현). reader가 죽으면 렌더러는 메시지가
1.5 s 넘게 끊긴 뒤 Gray·중립 표시 (0.25 s 확인 주기가 더해져 실측 약 1.6–1.7 s, §11), 렌더러가 죽어도 reader는 그대로. OBS plugin은 MVP에 넣지 않는다 (input-overlay는 GPL-2.0 — 참고만).

**지연에 영향을 주지 않기 위한 규칙 (설계 — 그 효과는 측정하지 않음, Unknown):** SetState·독점 open·훅·DLL 주입·포커스 변경 없음.
빈 slot은 2 s마다. 120 Hz(임시) 폴링 — 현재 구현 설정일 뿐 정확한 event timing·latency 측정이 아니다. 프로세스 우선순위
below-normal. 렌더러는 메시지가 올 때와 0.25 s마다만 그리고, 페이지가 안 보이면 그리지 않는다(최소화 중 실제로 멈추는지는 Untested).

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

### Phase 1 (구현·검증됨 — 판단 없음)

Phase 1은 **XInput slot 상태 viewer**다. 선택한 slot에서 `XInputGetState`가 돌려준 값을 그대로 그리고, 등은 그 값이 들어오고
있는지만 보인다. report·packet 도착 시각을 재지 않고(폴링 시각뿐, §2), 사용자·장치·게임에 대해 어떤 진단도 하지 않으며, slot의
출처(물리 패드·원시 입력·게임 출력)를 가리지 않는다. §11의 검증도 이 범위 — "그린 것이 slot 상태와 같은가", "끊김·재연결·빈 slot·
reader 정지에서 Gray가 되는가" — 만 확인했다.

| 색 | 조건 |
|---|---|
| Gray ○ | 서버 없음/1.5 s 넘게 메시지 없음 (실측 1.6–1.7 s) · 선택 slot에 패드 없음 · reader가 1 s 넘게 그 slot을 못 읽음 |
| Green ● | 선택 slot의 데이터가 들어오고 있음 — "좋음"도 "빠름"도 아니다 |
| Yellow/Red | 쓰지 않음 (모양만 정의됨) |

### Phase 3 (설계만 — 구현·검증 안 됨) — 개인 baseline 대비 상대적 일관성

아래는 모두 미래 설계다. 지금 코드에는 Yellow/Red 판정도, baseline도, 아래 신호의 계산도 없다.

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

## 6. Phase 2 (설계만 — 구현·검증 안 됨) — RAW / OUTPUT 이중 표시

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
- (미래 설계) Phase 3이 생기고 사용자가 켜면 세션 요약만:

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
   (설계 불변식. reader를 죽여도 Windows `joy.cpl`이 패드를 그대로 본 것까지만 확인했고, 게임으로는 검증하지 않았다 — §11.)
3. 패드 끊김은 overlay 상태(Gray)만 바꾼다 — 재연결 시도·장치 조작 없음.
4. 가상 패드·매퍼 기능이 없는 동안 gamepad 소유권을 바꾸지 않는다 — 장치를 만들지도 숨기지도 독점하지도 않는다.
5. RAW와 (미래의) OUTPUT을 섞어 표시하지 않는다 — 식별 전엔 `slot n · source unknown`.
6. 게임 지연·하드웨어 polling rate·피로·케이블·FPS를 쟀다고 말하지 않는다. 타임스탬프는 overlay가 읽은 시각.
7. 포커스를 바꾸지 않고, 합성 키 입력을 만들지 않는다.

## 9. 성공 기준

| Phase | 기준 | 확인 | 결과 (`9b516b0`, §11) |
|---|---|---|---|
| 1 | 입력이 보임 | `--demo`와 실제 패드로 모든 버튼, LT/RT 0–255, 스틱 4방향·대각 | 통과 — 대각선은 D-pad 위+오른쪽만, 스틱 가장자리 ±32767은 "위"만 도달 |
| 1 | 끊김·재연결 | 끊으면 다음 폴링에서 Gray, 다시 연결되면 ≤2 s(빈 slot 재확인 주기) 안 Green — demo는 30 s마다 3 s 끊김으로 재현 | 통과 — BT 패드 전원 끔 → Gray, 켬 → 같은 slot Green. 재연결 시간은 BT 연결 시간과 분리 안 됨 |
| 1 | 지연 무영향 | **직접 측정 불가(UNKNOWN)** — 간섭 경로 없음(소스 스캔) + overlay CPU 예산(임시 <1% 코어) | UNKNOWN — 소스 스캔 통과, CPU 미측정, 게임 미실행 |
| 1 | 장애 격리 | reader/렌더러 강제 종료해도 패드 입력 그대로 (다른 XInput 뷰어로 확인) | 통과 — reader 강제 종료 → 페이지 Gray, `joy.cpl` 입력 그대로; 탭 닫아도 reader 그대로 |
| 2 | 이중 표시 정확성 | 테스트용 가상 패드 + 물리 패드에서 RAW/OUTPUT 혼동 없음, 불확실하면 UNKNOWN | 미구현 |
| 2 | double input 없는 표시 | 같은 장치가 두 번 그려지지 않음 (또는 "같은 장치일 수 있음") | 미구현 |
| 2 | 소유권 표시 | 가상 장치 소유 프로세스·게임에 보일 수 있는 패드 수 | 미구현 |
| 3 | baseline 부족 → Gray | 새 프로필은 Gray 유지 | 미구현 |
| 3 | 상대 판정만 | 기준보다 좋은 값은 Yellow가 안 됨 | 미구현 |
| 3 | 오탐 억제 | 순간 spike를 넣은 재생 데이터에서 색 안 바뀜 | 미구현 |
| 3 | 원인 단정 없음 | UI·저장 파일 어디에도 원인 단어 없음 | 미구현 |

## 10. 남은 UNKNOWN

- Steam Input이 켜져 있으면 XInput에 보이는 건 Steam의 가상 출력 — 표시는 되지만 RAW가 아니다.
- 게임이 어느 slot을 읽는지. 다른 가상 패드가 같이 켜져 있으면 slot이 2개 → `slot=` 옵션으로 고르고 추측하지 않는다.
- 전용 전체화면에선 단독 창(Phase 1b)이 가려진다.
- OBS Browser Source에서 장시간(30분 이상) 동작·CPU·메모리는 아직 측정 안 함 (§11.5).
- §11 검증 뒤에도 남은 것: OBS 장시간·다른 OBS 버전, 다른 브라우저, 단축키(Ctrl+Shift+F10)를 게임이 앞에 있을 때 누르는 경우, Steam Input 켜짐,
  리매퍼·가상 패드(ViGEm 등) 공존, 여러 slot, 유선·동글 연결, 다른 패드, 장시간 CPU·메모리, 실제 게임 입력에 미치는 영향,
  창을 최소화했을 때 그리기가 실제로 멈추는지, 모든 축의 ±32767 가장자리.
- 이 도구는 원리상 재지 않는 것: 하드웨어 polling rate, 입력 지연, 게임 지연, FPS, 패드 상태(health), 물리/가상 장치 구분.

## 11. Phase 1 수동 검증 결과 (manual result, 2026-10-03, 코드 `9b516b0`)

이 절은 **설계가 아니라 한 번의 수동 실행에서 관찰한 결과**다. 라벨: **Verified**(확인함) · **Observed**(그 실행에서 잰 값,
보장 아님) · **Untested**(안 해 봄) · **Unknown**(분리·측정 못 함) · **Design only**(구현 안 됨). 이 환경 밖은 Untested.

### 11.1 환경

| 항목 | 값 |
|---|---|
| OS / Python | Windows 10.0.26200, Python 3.12.10 |
| 패드 | Xbox Series 패드 1개, Bluetooth, XInput slot 0 |
| 다른 소프트웨어 | Steam 실행 중, 이 패드의 Steam Input은 꺼짐. mapper·가상 패드·dsr-bot·게임·OBS 실행 안 함 |
| 렌더러 | Claude 데스크톱 앱 내장 브라우저 |
| 서버 | `127.0.0.1:47820`에서만 listen |
| 오프라인 테스트 | 23 passed |

### 11.2 Verified

- demo: full·compact·streamer, 가짜 끊김 → Gray(입력 중립) → Green, 새로고침.
- 매핑: 사람이 정해진 순서로 하나씩 누른 A, B, X, Y, LB, RB, View, Menu, L3, R3, D-pad 위·아래·왼쪽·오른쪽, 위+오른쪽 대각선이
  그 순서대로 해당 입력으로 관찰됨.
- LT·RT 모두 255 도달, 중간값도 관찰.
- 양쪽 스틱 상하좌우가 기대한 방향으로 표시(위 = +y, 왼쪽 = −x).
- compact·streamer를 실제 입력으로 확인.
- 패드 전원 끔 → slot 0 Gray. Bluetooth 재연결 뒤 같은 slot 0에서 Green, A 입력 관찰.
- 빈 slot(`slot=3`) → Gray, 켜진 버튼 없음.
- reader/server 정지 → 페이지가 stale Gray·입력 중립으로 전환.
- 렌더러 탭을 닫아도 reader 계속 동작.
- reader 정지 뒤에도 Windows `joy.cpl`이 패드를 계속 인식.
- 창 최소화 → 복원 뒤 누르지 않은 버튼이 켜진 것 없음.

### 11.3 Observed — 설계값과 실측값

모두 한 번의 실행에서 본 근삿값이다. latency 측정이나 성능 지표로 해석하지 않는다.

| 항목 | 설계값 (configured / target) | 실측 (observed) | 메모 |
|---|---|---|---|
| reader 정지 → Gray·중립 | stale threshold 1.5 s | 마지막 update 뒤 약 1.6–1.7 s | threshold에 client 쪽 주기 확인(0.25 s)·그리기 시점이 더해짐. "1.5 s 이내" 보장 아님 |
| 서버 재시작 → 열린 페이지 Green | (브라우저 EventSource 재연결에 맡김) | 약 1.8 s | |
| 패드 전원 끔 → 다시 Green | 빈 slot 재확인 2 s | 전체 왕복 약 12 s | 사용자 대기 약 5 s와 Bluetooth 재연결 포함 — overlay 자체 몫은 **Unknown** |
| raw 상태 vs 그린 버튼 | — | 약 4,993 draw frame에서 3 프레임 이상 불일치 0건 | raw XInput state와 overlay visual state의 정합성 관찰일 뿐, 물리 입력 → 게임·화면 end-to-end latency 측정이 아님 |
| 스틱 가장자리 | ±32767 | "위"만 도달, 나머지 방향은 0.82–0.96 | 모든 방향 full-scale은 Untested |

참고: reader는 두 번 다 강제 종료(프로세스 kill)로 멈췄고, Ctrl+C 종료 경로는 따로 확인하지 않았다. 서버가 꺼진 동안 콘솔엔
재연결 실패(네트워크 오류)만 있었고 스크립트 오류는 없었다.

### 11.4 Untested · Unknown

- Untested: OBS 30분 이상 장시간·소스 숨기기/보이기·다른 OBS 버전·OBS 안에서의 Gray/Green 전환 시간(§11.5), 게임이 앞에 있을 때의 Ctrl+Shift+F10 단축키(OBS가 앞에 있을 때는 Verified — 누를 때마다 숨기기·보이기 한 번씩),
  Steam Input 켜짐, mapper·가상 패드 동시 실행, 실제 게임과 함께 돌렸을 때 게임 입력 영향, 다른 브라우저, 여러 패드·slot,
  다른 패드 모델, 유선·무선 동글 연결, 30분 이상 리소스·안정성, 최소화 중 그리기가 실제로 멈추는지, 모든 스틱 방향의 full-scale.
- Unknown / 이 도구가 재지 않는 것: end-to-end latency, 입력 속도, 입력·패드 상태(health), 물리/가상 출처 구분,
  재연결 지연 중 overlay 몫.

### 11.5 OBS Browser Source (manual result, 2026-10-03, OBS 32.2.2)

같은 코드·Windows·Python·패드·slot·Steam Input 상태. 테스트 동안 게임·mapper·가상 패드는 실행하지 않음. 별도 장면에
밝은 회색 Color source를 깔고 그 위에 Browser source(localhost URL, Local file 아님, OBS 기본 custom CSS).

| 항목 | 결과 |
|---|---|
| 렌더링 | Verified — 배경 투명, 검은 사각형·눈에 띄는 halo·잘림·스크롤바 없음. 밝은 배경에선 얇은 테두리·deadzone 고리·작은 글씨가 잘 안 보임(대비 문제, alpha 문제 아님) |
| 입력 표시 | Verified — 버튼, D-pad(위+오른쪽 포함), LT/RT 절반·끝, 양쪽 스틱 4방향. 일부는 미리보기 캡처, 일부는 사용자 육안 확인, `/state` 기록과 대조 |
| 레이아웃 | Verified — full, compact, streamer(560×330). 누르면 표시되고 떼면 꺼짐 |
| 장면 전환 3회 | Verified — 돌아올 때마다 Green, 새 A 입력 표시 |
| reader 재시작 | Verified — 멈추면 Gray·중립, 다시 켜면 저절로 Green. 전환 시간은 OBS 안에서 재지 못함(Unknown) |
| OBS 재시작 | Verified — reader 영향 없음, 소스가 다시 연결되고 새 A 입력 표시 |
| 빈 slot(`slot=3`) | Verified — Gray, `no controller`, 켜진 버튼 없음 |
| 30분 장시간 | 실행 안 함 → Unknown |
| 실제 녹화 | 사용자 보고 — 다크소울 녹화 한 번에서 정확히 표시됐다고 함. 기록·캡처 없음. 게임 입력·성능에 대한 증거가 아님 |

참고: 테스트 중 패드가 한 번 XInput에서 사라졌다가 사용자가 다시 켠 뒤 돌아왔다. 원인은 Unknown(overlay는 읽기만 함).

## 12. 한계 (Limitations)

| 한계 | 뜻 |
|---|---|
| `XInputGetState`를 읽는 read-only observer일 뿐 | slot 상태를 보여 줄 뿐, 그 상태가 어디서 왔는지(물리 패드, Steam Input·mapper가 만든 변환·가상 XInput, 게임 출력, 다른 중간 계층) 가리지 않는다 |
| 게임 입력 비간섭은 게임 없이 증명할 수 없음 | 설계상 간섭 경로(쓰기·훅·주입·독점 open)는 없지만(소스 스캔), 실제 게임으로는 확인하지 않았다 |
| `joy.cpl` 확인의 범위 | reader 종료 뒤에도 Windows가 패드를 인식한다는 관찰일 뿐 — 모든 게임·안티치트·입력 경로에서의 안전을 보장하지 않는다 |
| 브라우저 결과의 일반화 불가 | 앱 내장 브라우저·OBS 32.2.2 결과를 다른 브라우저나 다른 OBS 버전으로 넓히지 않는다 |
| 120 Hz 폴링은 구현 설정 | 정확한 event timing이나 latency 측정이 아니다. 시각은 overlay가 읽은 시점이고, 두 번 읽는 사이에 생겼다 사라진 상태는 놓친다 |
| Phase 1b·2·3은 Design only | 단독 창, RAW/OUTPUT 구분, source classification, Yellow/Red, baseline, timing 관련 지표는 모두 구현·검증되지 않았다 |
