# ResQSEAT

---

# 🚗 Save First: 차량 사고 대응 자동화 시스템

> **ResQSeat 기반 연구 프로젝트 - 차량 탑승자 인식 및 사고 대응 자동화 시스템**
> 본 시스템은 차량 내 센서, 카메라, 임베디드 장치를 활용하여 사고 발생 시 탑승자 상태(착석 여부, 연령대, 의식 여부, 충격 강도 등)를 자동 판단하고,
> 위급도 기반 구조 우선순위를 계산하여 서버로 전송하는 통합 구조를 구현합니다.

---

## 📂 프로젝트 개요

| 구성 요소     | 설명                                                           |
| --------- | ------------------------------------------------------------ |
| **하드웨어**  | Arduino(센서 데이터 수집), Raspberry Pi(영상처리 및 메인 로직), 웹캠(연령·의식 판별) |
| **센서 입력** | 압력센서 (착석 여부), 가속도·자이로센서 (충격 감지)                              |
| **서버**    | Flask 기반 사고 데이터 수신·시각화 대시보드                                  |
| **결과 전송** | 사고 발생 시 JSON 데이터 및 현장 이미지 전송                                 |

---

## 🧭 전체 동작 흐름

### 🚦 사고 감지 전 단계

1. **`get_arduino_data.py`**

   * Arduino 2대와 시리얼 통신을 통해 **무게값(Weight)**, **충격값(mpu_g)** 데이터를 지속적으로 수신.
   * `g_latest_seat_data` 딕셔너리에 최신 좌석별 센서 데이터를 실시간 저장.
   * `tare`(영점 보정) 명령을 지원하며, 모든 시리얼 포트를 자동 재연결.

2. **`age.py`**

   * 웹캠을 4분할하여 각 좌석의 인물 얼굴을 인식하고 **연령대 판단** 수행.
   * 3초 이상 감지된 얼굴의 **최빈값 나이**를 기준으로 잠금(lock) 처리.
   * 반환 형식:
     `return (S1_age, S2_age, S3_age, S4_age)` →
     `0=성인 / 1=어린이 / 2=없음`

3. **`seat_status.py`**

   * Arduino에서 받은 **무게 데이터**와 `age.py`의 **연령 코드**를 이용해 좌석별 착석 여부 판별.
   * `5kg 이상 & 사람(성인/어린이)` → 착석으로 판단.
   * 반환 형식:
     `return (S1_sit, S2_sit, S3_sit, S4_sit)` → `0=공석 / 1=착석`

4. **`accident_flag.py`**

   * 지속적으로 가속도 데이터를 모니터링하며,
     임계값(G>1.1) 초과 시 **사고 발생 플래그** 발생.

---

### 💥 사고 감지 후 단계

1. **사고 감지 후 5초 대기**

   * 진동 안정화 및 프레임 안정화 시간 확보.

2. **`motion.py`**

   * 웹캠을 통해 4분할 ROI(좌석 구역)별 **움직임 분석** 수행.
   * 일정 시간 내 움직임이 없으면 `무의식 상태`로 판단.
   * 반환 형식:
     `return (S1_UC, S2_UC, S3_UC, S4_UC)` → `0=의식 있음 / 1=의식 없음`

3. **`impact_score.py`**

   * 충격 센서(mpu_g) 값을 기반으로 좌석별 **충격 점수(0–50)** 계산.
   * 인접 좌석 간 영향도를 가중합하여 현실적인 충격 분포 반영.

4. **`jsondata.py`**

   * 좌석별 (연령, 의식 여부, 충격값, 착석여부)를 종합해 **위급도 스코어 계산**:

     ```
     Sx_score = (어린이여부*10 + 의식여부*50 + 충격값) * 착석여부
     ```
   * 최종 JSON 형식:

     ```json
     {
       "seat1": {"is_child": true, "is_conscious": false, "impact": 35.4, "score": 85.4, "status": "occupied"},
       "seat2": {"is_child": false, "is_conscious": true, "impact": 10.1, "score": 10.1, "status": "occupied"},
       ...
     }
     ```

5. **`capture.py`**

   * 사고 당시 장면을 **웹캠으로 캡처**하고 Flask 서버로 업로드.
   * 사고 ID(`accident_id`)와 함께 전송됨.

---

### 🧩 통합 실행: `main.py`

모든 기능을 통합한 메인 스크립트로, 다음 순서로 자동 수행됩니다:

```
1️⃣ 아두이노 데이터 수집 스레드 실행
2️⃣ 사용자에게 초기 보정(Tare) 요청
3️⃣ age.py로 연령대 판단
4️⃣ seat_status.py로 착석 여부 판단
5️⃣ accident_flag.py로 사고 감시
6️⃣ 사고 발생 시 motion.py로 의식 상태 판별
7️⃣ impact_score.py로 충격 점수 계산
8️⃣ jsondata.py로 위급도 JSON 생성
9️⃣ 서버로 사고 데이터 전송 및 capture.py로 사진 업로드
```

---

## 🌐 서버 구성 (`server14.py`)

Flask 기반 웹 서버로, 사고 발생 정보를 시각화합니다.

### 주요 기능

| 기능                       | 설명                             |
| ------------------------ | ------------------------------ |
| `/api/accident_trigger`  | 라즈베리파이에서 보낸 사고 JSON 수신, 로그에 저장 |
| `/api/upload_image/<id>` | 사고 이미지 업로드 및 저장                |
| `/accidents`             | 전체 사고 기록 JSON 형식 조회            |
| `/player/<id>`           | 개별 사고 상세 페이지 렌더링               |
| `/image/<filename>`      | 이미지 직접 접근 경로                   |

---

## 🖥️ 웹 인터페이스

### 1. **index14.html**

* 사고 목록(시간, 날짜, 우선순위 점수)을 실시간으로 표시
* 5초마다 `/accidents` API로 데이터 자동 갱신
* 각 사고 클릭 시 “More Information” 버튼을 통해 상세 페이지 이동

### 2. **player14.html**

* 사고 ID별 세부 현황 표시
* 캡처 이미지 표시
* 좌석별 상태(착석/공석, 연령, 의식, 충격값, 점수) 시각화
* Tailwind CSS + Ewha Green 테마 사용

---

## 📦 폴더 구조

```
save_first_project/
│
├── main.py                # 전체 로직 실행 메인 코드
├── get_arduino_data.py    # Arduino 센서 데이터 수집
├── age.py                 # 웹캠 기반 연령 판별
├── seat_status.py         # 무게+연령 기반 착석 여부 판별
├── accident_flag.py       # 가속도 기반 사고 감지
├── motion.py              # 움직임 분석(의식 판별)
├── impact_score.py        # 충격 점수 계산
├── jsondata.py            # 위급도 스코어 JSON 생성
├── capture.py             # 사고 장면 캡처 및 업로드
│
├── server14.py            # Flask 서버
├── templates/
│   ├── index14.html       # 대시보드 화면
│   └── player14.html      # 사고 상세 화면
│
└── images/                # 업로드된 사고 현장 이미지 저장 폴더
```

---

## ⚙️ 실행 방법

### ① 라즈베리파이 측 (클라이언트)

```bash
python3 main.py
```

* Arduino 및 웹캠 연결 필수
* 프로그램 시작 후, 안내 메시지에 따라 보정 → 착석 → 감시 진행

### ② 서버 측 (Flask)

```bash
python3 server14.py
```

* 기본 포트: `5000`
* 브라우저에서 `http://<서버 IP>:5000` 접속

---

## 🧮 위급도 계산 로직 요약

| 항목     | 가중치   | 설명                    |
| ------ | ----- | --------------------- |
| 어린이 여부 | +10   | 어린이 좌석이면 가중치 부여       |
| 의식 없음  | +50   | 무의식 상태일 경우 높은 위험도로 판단 |
| 충격 강도  | 0–50  | 실제 G값 기반 실수형 점수       |
| 착석 여부  | 곱셈 요소 | 공석일 경우 계산에서 제외        |

최종 계산 예시:

```
S1_score = (어린이*10 + 의식없음*50 + 충격값) * 착석여부
```

---

## 🧩 주요 기술 스택

* **Python 3.11**
* **OpenCV** – 영상 처리, 움직임 감지, 얼굴 인식
* **facelib** – 연령/성별 추정 모델
* **PySerial** – Arduino 통신
* **Flask + Tailwind CSS** – 서버 및 웹 UI
* **Threading / JSON / Requests** – 병렬 처리 및 네트워크 통신

---

## 🔍 예시 시나리오

1. 시스템 시작 → `main.py` 실행
2. 사용자 착석 → `age.py`로 연령 확인, `seat_status.py`로 착석 감지
3. 사고 발생 → `accident_flag.py` 플래그 발생
4. `motion.py`로 움직임 분석 후 의식 판별
5. `impact_score.py`로 충격 점수 계산
6. `jsondata.py`로 위급도 산출 → Flask 서버 전송
7. `capture.py`로 사고 현장 캡처 업로드
8. 웹 대시보드(`index14.html`)에서 사고 정보 실시간 확인

---

## 📸 실행 예시

![Dashboard Example](https://github.com/your-repo/save_first_project/blob/main/docs/dashboard_example.png)

---

## 🏁 License

This project is for **academic and research purposes only**.
© 2025 Save First Project Team (Ewha Womans University)

---

원하면 이 README에 **구조 다이어그램 (데이터 흐름도)** 나 **실행 예시 캡처 섹션**도 추가할 수 있어.
그림 포함 버전으로 확장할까? (예: “센서 입력 → 메인 로직 → 서버 전송” 흐름도)


