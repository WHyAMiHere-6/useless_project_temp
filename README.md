<img width="1280" height="640" alt="git (1)" src="https://github.com/user-attachments/assets/8920b256-2ba8-4988-b824-5351134eb4bd" />



# Shut Eye Alarm 😴⏰

## Basic Details

### Team Name: SIMPLE MINDS

### Team Members

- Team Lead: **ANSHA MEHRIN M N** - MODEL ENGINEERING COLLEGE
- Member 2: **ABHAY ARAKKAL** - MODEL ENGINEERING COLLEGE



---

## Project Description

**Shut Eye Alarm** is a reverse alarm clock designed to make sure you
actually go to sleep instead of waking you up.

At the user's scheduled bedtime, the alarm starts ringing and continues
to annoy the user until an **ESP32-CAM detects that their eyes are closed**.

Using computer vision, the system checks whether the user appears to be
asleep. Once the eyes are detected as closed for a certain period, the
alarm turns off.

In short:

> **An alarm clock that annoys you until you sleep! 😂**

---

## The Problem (that doesn't exist)

We already have alarm clocks that wake people up.

But there is one extremely important problem that nobody asked us to solve:

### "What if I don't go to sleep?" 😭

People stay awake scrolling through their phones, watching videos,
talking, gaming, or simply refusing to sleep.

So we created a completely unnecessary solution to this completely
unnecessary problem.

---

## The Solution (that nobody asked for)

**Shut Eye Alarm** is a reverse alarm clock.

Instead of waking the user up, it makes sure the user actually goes to sleep.

At the scheduled bedtime:

1. The alarm starts buzzing.
2. The ESP32-CAM starts monitoring the user's face.
3. The camera checks the user's eyes using computer vision.
4. If the eyes are still open, the buzzer continues.
5. Once the system detects that the eyes are closed continuously for a
   specified period, the buzzer turns OFF.
6. The LED indicates the current system/alarm status.

Because apparently, **sleeping now needs verification.** 😂

---

# Technical Details

## Technologies/Components Used

### For Software

- Arduino/C++
- Arduino IDE
- ESP32 programming environment
- ESP32-CAM computer vision
- ESP32-compatible face/eye detection library or model
- Embedded image processing

> The exact computer vision library/model will be finalized and tested
> during the project build.

### For Hardware

- ESP32
- ESP32-CAM
- Buzzer
- Push button
- LED
- Jumper wires
- Breadboard
- USB/power supply

---

# Implementation

## System Flow

```text
              ┌────────────────────┐
              │   User sets        │
              │   bedtime/alarm    │
              └─────────┬──────────┘
                        │
                        ▼
              ┌────────────────────┐
              │   Bedtime reached  │
              └─────────┬──────────┘
                        │
                        ▼
              ┌────────────────────┐
              │    Buzzer ON 🔊    │
              └─────────┬──────────┘
                        │
                        ▼
              ┌────────────────────┐
              │   ESP32-CAM 📷     │
              │ Captures user's    │
              │ face                │
              └─────────┬──────────┘
                        │
                        ▼
              ┌────────────────────┐
              │   Eye Detection    │
              └─────────┬──────────┘
                        │
                  ┌─────┴─────┐
                  │           │
                  ▼           ▼
              Eyes Open    Eyes Closed
                  │           │
                  ▼           ▼
              Keep          Confirm
              buzzing       for a few
                            seconds
                                │
                                ▼
                         ┌─────────────┐
                         │  Buzzer OFF │
                         │     😴      │
                         └─────────────┘
