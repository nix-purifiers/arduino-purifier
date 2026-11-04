#include <ArduinoJson.h>
#include <Adafruit_GFX.h>
volatile int answer = 42;
void setup() { Serial.begin(9600); JsonDocument doc; doc["answer"] = answer; serializeJson(doc, Serial); }
void loop() { digitalWrite(LED_BUILTIN, answer & 1); }
