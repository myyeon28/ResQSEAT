#include <HX711.h>
#include <ArduinoJson.h>
#include <Wire.h>       // MPU6050용
#include <MPU6050.h>    // MPU6050용
#include <math.h>       // fabs, sqrt용

// ====== 이 보드(좌석1, 좌석2) 식별 ======
#define DEVICE_ID "arduino_A"
const char* SEAT_NAMES[2] = {"S1","S2"};

// ====== 핀 매핑 ======
// S1 (S1): DOUT -> D2,D3,D4,D5  / SCK -> D6(공통)
// S2 (S2): DOUT -> A0,A1,A2,A3  / SCK -> D13(공통)
const uint8_t DOUT_PINS[8] = {2,3,4,5,  A0,A1,A2,A3};
const uint8_t  SCK_PINS[8] = {6,6,6,6,  13,13,13,13};

HX711 hx[8];

// *** 파이썬 호환성을 위해 '좌석별' 스케일 사용 ***
float calibrationSeat[2] = {-58000.0f, -58000.0f};
float loadCell[8];

unsigned long lastSend = 0;
const unsigned long periodMs = 200; // 5Hz
const float NOISE_CUT_KG = 1.0f;    // 1kg 미만 0 처리

inline int chOf(int seatIdx, int cellIdx) { return seatIdx*4 + cellIdx; }

// --- 좌석별 보정/Tare 함수 
void applyCalibrationSeat(int s) {
  for (int c=0; c<4; c++) {
    hx[chOf(s,c)].set_scale(calibrationSeat[s]);
  }
}
void applyCalibrationAll() { applyCalibrationSeat(0); applyCalibrationSeat(1); }

void tareSeat(int s) { for (int c=0;c<4;c++) hx[chOf(s,c)].tare(); }
void tareAll()       { for (int i=0;i<8;i++)  hx[i].tare(); }

// --- auto_cal_seat용 raw-count 측정 함수 
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

// mpuS1 -> 좌석 1 (0x68)
// mpuS2 -> 좌석 2 (0x69)
MPU6050 mpuS1(0x68);
MPU6050 mpuS2(0x69);

float mpu_g[2] = {0.0f, 0.0f}; // S1, S2 합성가속도 (g)

float readG(MPU6050& mpu) {
  int16_t ax, ay, az;
  mpu.getAcceleration(&ax, &ay, &az);
  float gx = ax / 16384.0f, gy = ay / 16384.0f, gz = az / 16384.0f;
  return sqrt(gx*gx + gy*gy + gz*gz);
}


void setup() {
  Serial.begin(115200);
  Wire.begin(); 
  delay(50);

  // HX711 초기화 (begin만 호출)
  for (int i=0; i<8; i++) {
    hx[i].begin(DOUT_PINS[i], SCK_PINS[i]);
  }
  // setup 완료 후 보정/Tare 적용
  applyCalibrationAll();
  tareAll();

  // MPU 초기화
  mpuS1.initialize(); mpuS1.setSleepEnabled(false); mpuS1.setFullScaleAccelRange(MPU6050_ACCEL_FS_2);
  mpuS2.initialize(); mpuS2.setSleepEnabled(false); mpuS2.setFullScaleAccelRange(MPU6050_ACCEL_FS_2);

  delay(100);
}

void readLoads() {
  for (int i=0; i<8; i++) {
    float u = hx[i].get_units();
    loadCell[i] = (fabs(u) < NOISE_CUT_KG) ? 0.0f : u;
  }
}

void readMPUs() {
  mpu_g[0] = readG(mpuS1); // S1
  mpu_g[1] = readG(mpuS2); // S2
}

void sendJson() {
  StaticJsonDocument<1024> doc; // MPU 데이터 포함 위해 넉넉하게
  doc["device_id"] = DEVICE_ID;
  doc["ts_ms"] = millis();
  doc["unit"] = "kg";
  doc["cal_S1"] = calibrationSeat[0];
  doc["cal_S2"] = calibrationSeat[1];

  JsonArray flat = doc.createNestedArray("loadCell"); // "hx_loadCell" -> "loadCell"
  for (int i=0; i<8; i++) flat.add(loadCell[i]);

  JsonArray seats = doc.createNestedArray("seats");
  for (int s=0; s<2; s++) {
    float sum=0;
    JsonObject seat = seats.createNestedObject();
    seat["name"] = SEAT_NAMES[s];
    JsonArray w = seat.createNestedArray("loadCell"); // "hx_loadCell" -> "loadCell"
    for (int c=0; c<4; c++) { float v = loadCell[chOf(s,c)]; w.add(v); sum += v; }
    
    seat["Weight"] = sum;
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

void handleIncoming() {
  if (!Serial.available()) return;
  String line = Serial.readStringUntil('\n'); line.trim();
  if (line.length()==0) return;

  StaticJsonDocument<256> msg;
  if (deserializeJson(msg, line)) return;

  const char* cmd = msg["cmd"]; if (!cmd) return;

  if (strcmp(cmd,"set_cal_seat")==0 && msg.containsKey("seat") && msg.containsKey("value")) {
    const char* seatName = msg["seat"]; float val = msg["value"].as<float>();
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
    float new_cal = counts / wref;          // 새 보정값 계산
    calibrationSeat[idx] = new_cal;         // RAM에 임시 적용
    applyCalibrationSeat(idx);              // HX711 칩에 적용

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
  // 1. 명령 수신 (보정 명령 포함)
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