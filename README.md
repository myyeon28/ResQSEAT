# ResQSEAT

차량 사고 발생 시 탑승자 상태(착석 여부, 연령대, 의식 여부, 충격 강도)를 자동으로 추정하고, 우선 구조 대상 정보를 서버에 전송·시각화하는 시스템.

* Raspberry Pi: 메인 로직 실행
* Arduino: 센서 데이터 수집
* Webcam: 연령 추정, 의식 여부 판별
* Flask 서버: 사고 기록 및 대시보드


## 시스템 동작 흐름

### 1. 사고 감지 전

1. `get_arduino_data.py`

   * Arduino에서 좌석별 무게(Weight)와 충격값(mpu_g)을 지속적으로 수집.
   * 최신 값을 전역 딕셔너리(`g_latest_seat_data`)에 유지.
   * 시리얼 재연결, tare(영점 보정) 명령 지원.

2. `age.py`

   * 카메라 화면을 4개 구역(S1~S4)으로 나눠 얼굴을 감지.
   * 일정 시간(기본 3초) 동안 관측된 얼굴의 최빈 나이로 연령대 잠금.
   * 반환: `(S1_age, S2_age, S3_age, S4_age)`

     * `0 = 성인`, `1 = 어린이`, `2 = 빈 좌석`

3. `seat_status.py`

   * 무게값 + 연령 정보를 이용해 실제 착석 여부를 판별.
   * 기본 기준: 무게 > 5kg 이고, age가 성인/어린이일 때 착석으로 간주.
   * 반환: `(S1_sit, S2_sit, S3_sit, S4_sit)`

     * `0 = 공석`, `1 = 착석`

4. `accident_flag.py`

   * 좌석별 가속도(mpu_g)를 실시간 모니터링.
   * 특정 임계값(기본 1.1g) 초과 시 “사고 발생”으로 판단하고 해당 순간의 센서 스냅샷을 반환.

---

### 2. 사고 감지 후

1. 안정화 대기 (기본 5초)

2. `motion.py`

   * 동일한 4개 구역에 대해 움직임(프레임 차이)을 분석.
   * 움직임이 일정 시간 안에 없으면 “의식 없음”으로 판단.
   * 반환: `(S1_UC, S2_UC, S3_UC, S4_UC)`

     * `0 = 의식 있음`, `1 = 의식 없음`

3. `impact_score.py`

   * 사고 시점의 가속도 데이터를 이용해 좌석별 충격 점수(0~50)를 산출.
   * 좌석 간 가중치를 둬서 인접 좌석 충격도 반영.

4. `jsondata.py`

   * 좌석별 정보를 하나의 스코어로 통합:

     * 어린이: +10
     * 의식 없음: +50
     * 충격 점수: 0~50
     * 공석인 좌석은 0 처리
   * 최종 출력 예시:

     ```json
     {
       "seat1": {
         "is_child": true,
         "is_conscious": false,
         "impact": 35.4,
         "score": 85.4,
         "status": "occupied"
       },
       "seat2": {
         "is_child": false,
         "is_conscious": true,
         "impact": 10.1,
         "score": 10.1,
         "status": "occupied"
       },
       "seat3": {
         "status": "empty",
         "score": 0
       },
       "seat4": { ... }
     }
     ```

5. `capture.py`

   * 사고 직후 차량 내부(웹캠) 이미지를 캡처.
   * 서버에 업로드하여 사고 ID에 연결.

---

## 통합 실행 (`main.py`)

`main.py`는 전체 파이프라인을 순차적으로 실행한다.

흐름 요약:

1. Arduino 수집 스레드 시작 (`get_arduino_data.start_reader_threads()`)
2. 빈 좌석 상태에서 tare(무게 보정)
3. 탑승 완료 후 연령 추정 (`age.py`)
4. 착석 여부 판정 (`seat_status.py`)
5. 사고 발생까지 대기 (`accident_flag.py`)
6. 사고 발생 시:

   * 의식 판별 (`motion.py`)
   * 충격 점수 계산 (`impact_score.py`)
   * 좌석별 위험도/우선순위 JSON 구성 (`jsondata.py`)
   * 서버에 사고 보고 POST
   * 캡처 이미지 업로드 (`capture.py`)

---

## 서버 (`server14.py`)

Flask 기반 서버. Raspberry Pi에서 보낸 데이터를 받아서 저장하고 웹으로 보여준다.

주요 엔드포인트:

| 엔드포인트                         | 설명                                      |
| ----------------------------- | --------------------------------------- |
| `POST /api/accident_trigger`  | 사고 데이터(JSON) 수신, 내부 로그에 저장. 고유 ID 발급.   |
| `POST /api/upload_image/<id>` | 사고 ID에 해당하는 현장 이미지 업로드.                 |
| `GET /accidents`              | 전체 사고 로그(JSON) 조회. 대시보드가 주기적으로 polling. |
| `GET /player/<id>`            | 특정 사고 상세 페이지 렌더링.                       |
| `GET /image/<filename>`       | 업로드된 사고 이미지 제공.                         |

데이터는 메모리 내 리스트(`ACCIDENT_LOG`)에 유지된다.
서버는 Tailwind CSS 기반 템플릿(`index14.html`, `player14.html`)을 통해 웹 UI를 제공한다.

* `index14.html`

  * 사고 발생 시간, 최대 위험도 점수, 상세 페이지 링크 리스트업
  * `/accidents`를 주기적으로 불러와 자동 갱신

* `player14.html`

  * 좌석별 상태(착석 여부, 성인/어린이, 의식 여부, 충격값, 최종 점수) 시각화
  * 사고 당시 캡처 이미지 표시


---

## 실행 방법

### Raspberry Pi 측 (클라이언트)

```bash
python3 main.py
```

사전 조건:

* Raspberry Pi에 웹캠 연결
* Arduino(압력/가속도 센서) USB 연결
* `SERVER_BASE_URL`이 서버 주소로 설정되어 있어야 함 (`main.py` 상단)

실행 중 콘솔에서 순서대로:

* tare 캘리브레이션 지시
* 착석 후 계속 진행
* 이후 사고 감시/보고 자동 수행

### 서버 측 (Flask)

```bash
python3 server14.py
```

* 기본 포트: `5000`
* 브라우저에서 `http://<서버 IP>:5000` 접속
* `/` : 실시간 사고 로그 대시보드
* `/player/<accident_id>` : 상세 화면

---

## 점수 계산 기준

좌석별 최종 점수(`score`)는 아래 요소로 구성된다:

* 어린이 좌석: +10
* 의식 없음: +50
* 충격 강도 점수: 0~50 (센서 기반)
* 공석일 경우 전체 점수는 0 처리

예:

```text
score = (child*10 + unconscious*50 + impact) * occupied
```


---


* Python 3.11
* OpenCV (`cv2`)
* facelib (age estimation)
* PySerial
* Flask
* requests
* threading / time / json 표준 라이브러리

(프로젝트 환경은 Raspberry Pi + Arduino 기준으로 작성되었음)

---
