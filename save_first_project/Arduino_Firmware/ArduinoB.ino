#include <HX711.h>
#include <ArduinoJson.h>
#include <Wire.h>
#include <MPU6050.h>
#include <math.h> 

// ====== 이 보드(좌석 S3, S4) 식별 ======
#define DEVICE_ID "arduino_B"
const char* SEAT_NAMES[2] = {"S3","S4"}; // 이름 통일 (S3, S4)

// ====== 핀 매핑 ======
// seat3 (S3): DOUT -> D2,D3,D4,D5  / SCK -> D6(공통)
// seat4 (S4): DOUT -> A0,A1,A2,A3  / SCK -> D13(공통)
const uint8_t DOUT_PINS[8] = {2,3,4,5,   A0,A1,A2,A3};
const uint8_t  SCK_PINS[8] = {6,6,6,6,   13,13,13,13};

HX711 hx[8];

// [수정] 공통 스케일 대신 '좌석별' 스케일 사용 (A와 동일)
float calibrationSeat[2] = {-52000.0f, -52000.0f};
float loadCell[8];

unsigned long lastSend = 0;
const unsigned long periodMs = 200; // 5Hz
const float NOISE_CUT_KG = 1.0f;    // 1kg 미만 0 처리

inline int chOf(int seatIdx, int cellIdx) { return seatIdx*4 + cellIdx; }

// --- [추가] 좌석별 보정/Tare 함수 (A에서 복사) ---
void applyCalibrationSeat(int s) {
  for (int c=0; c<4; c++) {
    hx[chOf(s,c)].set_scale(calibrationSeat[s]);
  }
}
// [수정] A와 동일한 방식으로 변경
void applyCalibrationAll() { applyCalibrationSeat(0); applyCalibrationSeat(1); }

void tareSeat(int s)       { for (int c=0;c<4;c++) hx[chOf(s,c)].tare(); }
void tareAll()             { for (int i=0;i<8;i++) hx[i].tare(); }

// --- [추가] auto_cal_seat용 raw-count 측정 함수 (A에서 복사) ---
float measureSeatCounts(int s, int samples = 20, int interDelayMs = 5) {
  double acc = 0.0;
  for (int k=0; k<samples; k++) {
    long seat_counts = 0;
    for (int c=0; c<4; c++) seat_counts += hx[chOf(s,c)].get_value(1);
    acc += (double)seat_counts;
    delay(interDelayMs);
  }
  return (float)(acc / samples);
}


// ===== MPU6050 (BACK sensors) =====
// mpuS3 -> 좌석 S3, 주소 0x68 (AD0 = GND)
// mpuS4 -> 좌석 S4, 주소 0x69 (AD0 = VCC)
MPU6050 mpuS3(0x68);
MPU6050 mpuS4(0x69);

float mpu_g[2] = {0.0f, 0.0f}; // S3, S4 합성가속도 (g)

// MPU6050 센서로부터 합성 가속도(g) 값을 읽는 함수
float readG(MPU6050& mpu) {
  int16_t ax, ay, az;
  mpu.getAcceleration(&ax, &ay, &az);
  // ±2g 가정: 1g ≈ 16384 LSB
  float gx = ax / 16384.0f, gy = ay / 16384.0f, gz = az / 16384.0f;
  return sqrt(gx*gx + gy*gy + gz*gz);
}

void setup() {
  Serial.begin(115200);
  Wire.begin(); // MPU6050(I2C)을 위해 Wire 라이브러리 시작
  delay(50);

  // [수정] HX711 초기화 (begin만 호출 - A와 동일)
  for (int i=0; i<8; i++) {
    hx[i].begin(DOUT_PINS[i], SCK_PINS[i]);
  }
  // [수정] setup 완료 후 보정/Tare 적용 (A와 동일)
  applyCalibrationAll();
  tareAll();

  // MPU 초기화
  mpuS3.initialize(); mpuS3.setSleepEnabled(false); mpuS3.setFullScaleAccelRange(MPU6050_ACCEL_FS_2);
  mpuS4.initialize(); mpuS4.setSleepEnabled(false); mpuS4.setFullScaleAccelRange(MPU6050_ACCEL_FS_2);

  // 작은 안정화 지연
  delay(100);
}

// 8개 로드셀 값을 읽어 loadCell 배열에 저장
void readLoads() {
  for (int i=0; i<8; i++) {
    float u = hx[i].get_units();
    // [수정] u < NOISE_CUT_KG -> fabs(u) < NOISE_CUT_KG 로 변경
    loadCell[i] = (fabs(u) < NOISE_CUT_KG) ? 0.0f : u;
  }
}

// 2개 MPU 값을 읽어 mpu_g 배열에 저장
void readMPUs() {
  // S3: mpuS3, S4: mpuS4
  mpu_g[0] = readG(mpuS3);
  mpu_g[1] = readG(mpuS4);
}

// JSON 데이터를 시리얼로 전송
void sendJson() {
  // JSON 크기 여유 두기 (코드 A와 동일하게 1024)
  StaticJsonDocument<1024> doc;
  doc["device_id"] = DEVICE_ID;
  doc["ts_ms"] = millis();
  doc["unit"] = "kg";
  
  // [수정] A와 형식은 맞추되, B의 좌석 이름(S3, S4)을 사용
  doc["cal_S3"] = calibrationSeat[0];
  doc["cal_S4"] = calibrationSeat[1];

  // "hx_weights" -> "loadCell" (arduino_A와 통일)
  JsonArray flat = doc.createNestedArray("loadCell");
  for (int i=0; i<8; i++) flat.add(loadCell[i]);

  JsonArray seats = doc.createNestedArray("seats");
  for (int s=0; s<2; s++) {
    float sum=0;
    JsonObject seat = seats.createNestedObject();
    seat["name"] = SEAT_NAMES[s]; // "S3" 또는 "S4"
    
    // "hx_weights" -> "loadCell" (arduino_A와 통일)
    JsonArray w = seat.createNestedArray("loadCell"); 
    for (int c=0; c<4; c++) { float v = loadCell[chOf(s,c)]; w.add(v); sum += v; }
    
    seat["Weight"] = sum; 

    // mpu_g: 좌석별 MPU 값
    seat["mpu_g"] = mpu_g[s];

    char key[32];
    snprintf(key, sizeof(key), "%s_Weight", SEAT_NAMES[s]);
    doc[key] = sum;
    snprintf(key, sizeof(key), "%s_mpu_g", SEAT_NAMES[s]);
    doc[key] = mpu_g[s];
  }

  serializeJson(doc, Serial);
  Serial.println();
}

// [수정] 시리얼 명령 처리: Arduino A의 handleIncoming() 함수를 그대로 복사
// (SEAT_NAMES이 {"S3", "S4"} 이므로 S3, S4에 대해 정상 동작함)
void handleIncoming() {
  if (!Serial.available()) return;
  String line = Serial.readStringUntil('\n'); line.trim();
  if (line.length()==0) return;

  StaticJsonDocument<256> msg;
  if (deserializeJson(msg, line)) return;

  const char* cmd = msg["cmd"]; if (!cmd) return;

  if (strcmp(cmd,"set_cal_seat")==0 && msg.containsKey("seat") && msg.containsKey("value")) {
    const char* seatName = msg["seat"]; float val = msg["value"].as<float>();
    // SEAT_NAMES[0] = "S3", SEAT_NAMES[1] = "S4"
    int idx = (!strcmp(seatName,SEAT_NAMES[0]))?0:(!strcmp(seatName,SEAT_NAMES[1]))?1:-1;
    if (idx>=0) {
      calibrationSeat[idx] = val; applyCalibrationSeat(idx);
      StaticJsonDocument<120> ack; ack["ack"]="set_cal_seat"; ack["seat"]=SEAT_NAMES[idx]; ack["value"]=val;
      serializeJson(ack, Serial); Serial.println();
    }

  } else if (strcmp(cmd,"auto_cal_seat")==0 && msg.containsKey("seat") && msg.containsKey("wref")) {
    const char* seatName = msg["seat"]; float wref = msg["wref"].as<float>();
    int idx = (!strcmp(seatName,SEAT_NAMES[0]))?0:(!strcmp(seatName,SEAT_NAMES[1]))?1:-1;
    if (idx<0 || wref<=0.0f) {
      StaticJsonDocument<96> err; err["ack"]="auto_cal_seat"; err["error"]="bad_args";
      serializeJson(err, Serial); Serial.println(); return;
    }
    
    float counts = measureSeatCounts(idx, 20, 5); 
    
    if (fabs(counts) < 10000.0f) {
      StaticJsonDocument<160> err;
      err["ack"]="auto_cal_seat"; err["seat"]=SEAT_NAMES[idx];
      err["wref"]=wref; err["error"]="no_load_detected_or_too_small"; err["counts_abs"]=fabs(counts);
      serializeJson(err, Serial); Serial.println(); return;
    }
    float new_cal = counts / wref;        // 새 보정값 계산
    calibrationSeat[idx] = new_cal;       // RAM에 임시 적용
    applyCalibrationSeat(idx);            // HX711 칩에 적용

    // *** 파이썬(Pi)으로 결과 보고 (저장 요청) ***
    StaticJsonDocument<200> ack;
    ack["ack"]="auto_cal_seat"; ack["seat"]=SEAT_NAMES[idx]; ack["wref"]=wref;
    ack["counts_total"]=counts; ack["new_cal"]=new_cal;
    serializeJson(ack, Serial); Serial.println();

  } else if (strcmp(cmd,"tare_seat")==0 && msg.containsKey("seat")) {
    const char* seatName = msg["seat"];
    int idx = (!strcmp(seatName,SEAT_NAMES[0]))?0:(!strcmp(seatName,SEAT_NAMES[1]))?1:-1;
    if (idx>=0) { tareSeat(idx); StaticJsonDocument<96> ack; ack["ack"]="tare_seat"; ack["seat"]=SEAT_NAMES[idx]; serializeJson(ack, Serial); Serial.println(); }

  } else if (strcmp(cmd,"tare")==0) {
    tareAll(); StaticJsonDocument<64> ack; ack["ack"]="tare"; serializeJson(ack, Serial); Serial.println();

  } else if (strcmp(cmd,"set_cal")==0 && msg.containsKey("value")) {
    float v = msg["value"].as<float>();
    calibrationSeat[0]=calibrationSeat[1]=v; applyCalibrationAll();
    StaticJsonDocument<96> ack; ack["ack"]="set_cal"; ack["value"]=v; serializeJson(ack, Serial); Serial.println();
  }
}


void loop() {
  // 시리얼 명령 수신 처리
  handleIncoming(); 
  
  unsigned long now = millis();
  if (now - lastSend >= periodMs) {
    lastSend = now;

    // 2. 로드셀 읽기 (I2C 방해 방지)
    readLoads();
  
    // 3. MPU 읽기 (I2C)
    readMPUs();   
    
    // 4. JSON 전송
    sendJson();
  }
}
