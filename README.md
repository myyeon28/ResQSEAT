# ResQSEAT

차량 사고 발생 시 탑승자 상태(착석 여부, 연령대, 의식 여부, 충격 강도)를 자동으로 추정하고, 우선 구조 대상 정보를 서버에 전송·시각화하는 시스템.

* Raspberry Pi: 메인 로직 실행
* Arduino: 센서 데이터 수집
* Webcam: 연령 추정, 의식 여부 판별
* Flask 서버: 사고 기록 및 대시보드

<br>

## 시스템 동작 흐름

### 1. 사고 감지 전

1. ***get_arduino_data.py***

   * Arduino에서 좌석별 무게(Weight)와 충격값(mpu_g)을 지속적으로 수집.
   * 최신 값을 전역 딕셔너리(***g_latest_seat_data***)에 유지.
   * 시리얼 재연결, tare(영점 보정) 명령 지원.

2. ***age.py***

   * 카메라 화면을 4개 구역(S1~S4)으로 나눠 얼굴을 감지.
   * 일정 시간(기본 3초) 동안 관측된 얼굴의 최빈 나이로 연령대 잠금.
   * 반환: ***(S1_age, S2_age, S3_age, S4_age)***

     * ***0 = 성인***, ***1 = 어린이***, ***2 = 빈 좌석***

3. ***seat_status.py***

   * 무게값 + 연령 정보를 이용해 실제 착석 여부를 판별.
   * 기본 기준: 무게 > 5kg 이고, age가 성인/어린이일 때 착석으로 간주.
   * 반환: ***(S1_sit, S2_sit, S3_sit, S4_sit)***

     * ***0 = 공석***, ***1 = 착석***

4. ***accident_flag.py***

   * 좌석별 가속도(mpu_g)를 실시간 모니터링.
   * 특정 임계값(기본 1.1g) 초과 시 “사고 발생”으로 판단하고 해당 순간의 센서 스냅샷을 반환.

<br>


### 2. 사고 감지 후

1. 안정화 대기 (기본 5초)

2. ***motion.py***

   * 동일한 4개 구역에 대해 움직임(프레임 차이)을 분석.
   * 움직임이 일정 시간 안에 없으면 “의식 없음”으로 판단.
   * 반환: ***(S1_UC, S2_UC, S3_UC, S4_UC)***

     * ***0 = 의식 있음***, ***1 = 의식 없음***

3. ***impact_score.py***

   * 사고 시점의 가속도 데이터를 이용해 좌석별 충격 점수(0~50)를 산출.
   * 좌석 간 가중치를 둬서 인접 좌석 충격도 반영.

4. ***jsondata.py***

   * 좌석별 정보를 하나의 스코어로 통합:

     * 어린이: +10
     * 의식 없음: +50
     * 충격 점수: 0~50
     * 공석인 좌석은 0 처리
   
5. ***capture.py***

   * 사고 직후 차량 내부(웹캠) 이미지를 캡처.
   * 서버에 업로드하여 사고 ID에 연결.

<br><br>

## 서버 (***server14.py***)

Flask 기반 서버. Raspberry Pi에서 보낸 데이터를 받아서 저장하고 웹으로 보여준다.

주요 엔드포인트:

| 엔드포인트                         | 설명                                      |
| ----------------------------- | --------------------------------------- |
| POST /api/accident_trigger  | 사고 데이터(JSON) 수신, 내부 로그에 저장. 고유 ID 발급.   |
| POST /api/upload_image/<id> | 사고 ID에 해당하는 현장 이미지 업로드.                 |
| GET /accidents              | 전체 사고 로그(JSON) 조회. 대시보드가 주기적으로 polling. |
| GET /player/<id>            | 특정 사고 상세 페이지 렌더링.                       |
| GET /image/<filename>       | 업로드된 사고 이미지 제공.                         |


* ***index14.html***

  * 사고 발생 시간, 최대 위험도 점수, 상세 페이지 링크 리스트업
  * ***/accidents***를 주기적으로 불러와 자동 갱신

* ***player14.html***

  * 좌석별 상태(착석 여부, 성인/어린이, 의식 여부, 충격값, 최종 점수) 시각화
  * 사고 당시 캡처 이미지 표시

<br><br>

## 점수 계산 기준

좌석별 최종 점수(***score***)는 아래 요소로 구성된다:

* 어린이 좌석: +10
* 의식 없음: +50
* 충격 강도 점수: 0~50 (센서 기반)
* 공석일 경우 전체 점수는 0 처리

<br>

## 필요 패키지

* Python 3.11
* OpenCV (`cv2`)
* facelib (age estimation)
* PySerial
* Flask
* requests
* threading / time / json 표준 라이브러리

(프로젝트 환경은 Raspberry Pi + Arduino Nano 기준으로 작성되었음)

---

## 📄 오픈소스 라이선스 고지 (Open Source License Notice)

본 프로젝트에는 다음 오픈소스 소프트웨어가 포함되어 있습니다.

- **FaceLib**  
  - Repository: [https://github.com/sajjjadayobi/FaceLib](https://github.com/sajjjadayobi/FaceLib)  
  - License: MIT License  
  - Copyright (c) 2020 Sajjad Ayobi

FaceLib는 얼굴 인식 및 연령/성별 추정을 위한 오픈소스 라이브러리로,  
본 프로젝트에서는 `AgeGenderEstimator`, `FaceDetector` 모듈에 활용되었습니다.  
원저작자의 MIT 라이선스 조건을 준수하며,  
라이선스 전문은 본 프로젝트의 `LICENSE` 파일에 포함되어 있습니다.



