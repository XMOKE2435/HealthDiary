# Hardware Connection Guide for HealthDiary

## Components
- **ICS-43434**: I2S digital microphone board
- **MAX98357A**: I2S 3W Class D amplifier/DAC breakout
- **Speaker**: Standard speaker (4-8 ohm recommended)

---

## Pin Connections

### ICS-43434 Microphone Board Connections

The ICS-43434 uses I2S (Inter-IC Sound) protocol. Connect to Raspberry Pi GPIO pins:

| ICS-43434 Pin | Raspberry Pi GPIO Pin | Physical Pin # | Function |
|---------------|----------------------|----------------|----------|
| 3V (Power)    | 3.3V                 | Pin 1 or 17    | Power (3.3V) - **IMPORTANT: Use 3.3V, NOT 5V!** |
| GND           | Ground (GND)         | Pin 6, 9, 14, 20, 25, 30, 34, 39 | Ground |
| SEL/LRCL      | GPIO 19              | Pin 35         | Word Select / Left-Right Clock (LRCLK) |
| BCLK          | GPIO 18              | Pin 12         | Bit Clock (Serial Clock) |
| DOUT          | GPIO 20              | Pin 38         | Data Output (Serial Data) |

**Pin Label Reference**:
- **3V** = 3.3V power supply (connect to Pin 1 or 17 on Raspberry Pi)
- **GND** = Ground (connect to any GND pin)
- **SEL/LRCL** = Word Select / Left-Right Clock (also called WS or LRCLK)
- **BCLK** = Bit Clock (also called SCK or Serial Clock)
- **DOUT** = Data Output (also called SD or Serial Data)

---

### MAX98357A Amplifier Board Connections

The MAX98357A also uses I2S protocol. Connect to Raspberry Pi GPIO pins:

| MAX98357A Pin | Raspberry Pi GPIO Pin | Physical Pin # | Function |
|---------------|----------------------|----------------|----------|
| VIN (Power)   | 5V                   | Pin 2 or 4     | Power (5V) |
| GND           | Ground (GND)         | Pin 6, 9, 14, 20, 25, 30, 34, 39 | Ground |
| LRC (Left/Right Clock) | GPIO 19    | Pin 35         | LRCLK |
| BCLK (Bit Clock) | GPIO 18          | Pin 12         | BCLK |
| DIN (Data In) | GPIO 21              | Pin 40         | Data Input |
| GAIN (optional) | Leave unconnected or connect to GND for default gain | | Gain setting |

**Note**: The MAX98357A typically has these pins:
- **VIN**: Power input (5V recommended)
- **GND**: Ground
- **LRC**: Left/Right Clock (Word Select)
- **BCLK**: Bit Clock
- **DIN**: Digital Audio Data Input
- **GAIN**: Gain control (can be left floating or tied to GND for default)

---

### Speaker Connections

Connect the speaker to the MAX98357A board:

| Speaker Wire | MAX98357A Terminal | Notes |
|--------------|-------------------|-------|
| Positive (+) | OUT+ or Speaker+ | Red wire or positive terminal |
| Negative (-) | OUT- or Speaker- | Black wire or negative terminal |

**Speaker Requirements**:
- **Impedance**: 4-8 ohms recommended
- **Power**: Up to 3W (MAX98357A output)
- **Type**: Any standard dynamic speaker

---

## Complete Wiring Diagram

```
Raspberry Pi GPIO Header:
                   3.3V  [1]  [2]  5V
                GPIO 2  [3]  [4]  5V
                GPIO 3  [5]  [6]  GND  ←───┐
                GPIO 4  [7]  [8]  GPIO 14   │
                   GND  [9]  [10] GPIO 15   │
               GPIO 17 [11]  [12] GPIO 18 ←─┼─── BCLK (Both ICS-43434 & MAX98357A)
               GPIO 27 [13]  [14] GND  ←───┤
               GPIO 22 [15]  [16] GPIO 23   │
                   3.3V [17]  [18] GPIO 24   │
               GPIO 10 [19]  [20] GND  ←───┤
                GPIO 9 [21]  [22] GPIO 25   │
               GPIO 11 [23]  [24] GPIO 8    │
                   GND [25]  [26] GPIO 7    │
                GPIO 0 [27]  [28] GPIO 1    │
                GPIO 5 [29]  [30] GND  ←───┤
                GPIO 6 [31]  [32] GPIO 12   │
               GPIO 13 [33]  [34] GND  ←───┤
               GPIO 19 [35] ←───────────────┼─── LRC/WS (Both ICS-43434 & MAX98357A)
               GPIO 16 [36]  [37] GPIO 26   │
               GPIO 20 [38] ←───────────────┘   DOUT (ICS-43434 Data Out)
                   GND [39] ←─── GND (All)      │
               GPIO 21 [40] ←───────────────────┘   DIN (MAX98357A Data In)

ICS-43434 Microphone:
    3V  ────→ 3.3V (Pin 1 or 17)
    GND ────→ GND (Pin 6, 9, 14, 20, 25, 30, 34, or 39)
    SEL/LRCL ────→ GPIO 19 (Pin 35)
    BCLK ────→ GPIO 18 (Pin 12)
    DOUT ────→ GPIO 20 (Pin 38)

MAX98357A Amplifier:
    VIN ────→ 5V (Pin 2 or 4)
    GND ────→ GND (Pin 6, 9, 14, 20, 25, 30, 34, or 39)
    LRC ────→ GPIO 19 (Pin 35)
    BCLK ───→ GPIO 18 (Pin 12)
    DIN ────→ GPIO 21 (Pin 40)
    GAIN ───→ Leave unconnected or connect to GND

Speaker:
    + ────→ MAX98357A OUT+ (or Speaker+)
    - ────→ MAX98357A OUT- (or Speaker-)
```

---

## Step-by-Step Connection Instructions

### Step 1: Power Off Your Raspberry Pi
**IMPORTANT**: Always power off your Raspberry Pi before making connections to avoid damage.

### Step 2: Connect Ground (GND) First
- Connect **all GND pins** together (common ground):
  - ICS-43434 GND → Raspberry Pi GND (Pin 6, 9, 14, 20, 25, 30, 34, or 39)
  - MAX98357A GND → Same Raspberry Pi GND pin
  - You can use a breadboard or connect multiple wires to the same GND pin

### Step 3: Connect Power
- **ICS-43434 3V** → Raspberry Pi **3.3V** (Pin 1 or 17)
- **MAX98357A VIN** → Raspberry Pi **5V** (Pin 2 or 4)

**Important**: 
- ICS-43434 needs 3.3V (do NOT connect to 5V - it will damage the microphone)
- MAX98357A needs 5V (it can handle 5V)

### Step 4: Connect I2S Clock Signals (Shared)
Both devices share the same clock signals:
- **BCLK**: Connect both ICS-43434 BCLK and MAX98357A BCLK to **GPIO 18 (Pin 12)**
- **SEL/LRCL**: Connect ICS-43434 SEL/LRCL and MAX98357A LRC to **GPIO 19 (Pin 35)**

### Step 5: Connect Data Lines (Separate)
- **ICS-43434 DOUT (Data Out)** → **GPIO 20 (Pin 38)** - Microphone sends data TO Pi
- **MAX98357A DIN (Data In)** → **GPIO 21 (Pin 40)** - Pi sends data TO amplifier

### Step 6: Connect Speaker
- Speaker positive (+) → MAX98357A OUT+ (or Speaker+ terminal)
- Speaker negative (-) → MAX98357A OUT- (or Speaker- terminal)

**Polarity matters**: Make sure positive connects to positive, negative to negative.

### Step 7: Verify Connections
Double-check all connections before powering on:
- [ ] All GND connected
- [ ] ICS-43434 3V → 3.3V (NOT 5V!)
- [ ] MAX98357A VIN → 5V
- [ ] Clock signals: ICS-43434 BCLK and SEL/LRCL connected, MAX98357A BCLK and LRC connected
- [ ] Data lines: ICS-43434 DOUT → GPIO 20, MAX98357A DIN → GPIO 21
- [ ] Speaker connected to MAX98357A output terminals

---

## Important Notes

### ⚠️ Safety Warnings

1. **Power Supply**: 
   - ICS-43434 uses 3.3V - connecting to 5V will damage it
   - MAX98357A uses 5V - this is correct
   - Double-check voltage before connecting

2. **GPIO Pins**:
   - GPIO pins are 3.3V logic level - do NOT connect 5V signals directly
   - The MAX98357A accepts 3.3V logic levels on its digital inputs, so this is fine

3. **Current Draw**:
   - Ensure your Raspberry Pi power supply can handle the additional load
   - MAX98357A can draw up to ~500mA at full volume
   - Use a good quality 5V 2.5A+ power supply for Raspberry Pi

4. **Short Circuits**:
   - Be careful not to short power to ground
   - Use proper jumper wires or a breadboard
   - Double-check all connections before powering on

### Physical Pin Numbering

Raspberry Pi GPIO pins are numbered in two ways:
- **Physical/Board pin numbers**: 1-40 (sequential numbering)
- **GPIO/Broadcom numbers**: GPIO 2, GPIO 3, etc.

**Important pins for this setup**:
- Pin 1: 3.3V (ICS-43434 3V pin)
- Pin 2: 5V (MAX98357A power)
- Pin 6: GND
- Pin 12: GPIO 18 (BCLK - shared by both devices)
- Pin 35: GPIO 19 (SEL/LRCL for ICS-43434, LRC for MAX98357A - shared)
- Pin 38: GPIO 20 (ICS-43434 DOUT)
- Pin 40: GPIO 21 (MAX98357A DIN)

### I2S Pin Sharing

Since both devices use I2S:
- **Clock signals (BCLK and LRC/WS) are shared** - both devices connect to the same GPIO pins
- **Data lines are separate** - microphone sends on GPIO 20, amplifier receives on GPIO 21
- This is standard I2S configuration - multiple devices can share clock signals

---

## After Hardware Connection

Once all connections are made:

1. **Power on Raspberry Pi**
2. **Enable I2S interface** (see software configuration steps)
3. **Test the connections** (see testing steps in RASPBERRY_PI_SETUP.md)

---

## Troubleshooting

### No Sound from Speaker
- Check speaker connections (polarity matters)
- Verify MAX98357A power (5V on VIN)
- Check DIN connection to GPIO 21
- Verify clock signals (BCLK and LRC) are connected
- Test with: `aplay -D hw:0,0 /usr/share/sounds/alsa/Front_Left.wav`

### Microphone Not Detected
- Verify ICS-43434 power (3.3V on 3V pin, NOT 5V!)
- Check DOUT connection to GPIO 20
- Verify clock signals (BCLK and SEL/LRCL) are connected
- Check all ground connections
- Test with: `arecord -D hw:1,0 -f cd test.wav`

### Distorted Audio
- Check power supply quality (use good quality 5V 2.5A+ supply)
- Verify speaker impedance (4-8 ohms recommended)
- Check for loose connections
- Reduce volume if clipping

### Device Not Recognized
- Verify I2S is enabled in Raspberry Pi configuration
- Check that clock and data lines are not swapped
- Verify GPIO pin numbers match physical connections
- Use `arecord -l` and `aplay -l` to list devices

---

## Next Steps

After hardware is connected, proceed to:
1. **Enable I2S interface** on Raspberry Pi (see RASPBERRY_PI_SETUP.md)
2. **Configure audio devices** in software
3. **Test microphone and speaker**
4. **Configure your HealthDiary application**

---

## Reference: Raspberry Pi GPIO Pinout

```
    3.3V  [1]  [2]  5V
 GPIO 2  [3]  [4]  5V
 GPIO 3  [5]  [6]  GND
 GPIO 4  [7]  [8]  GPIO 14
    GND  [9]  [10] GPIO 15
GPIO 17 [11]  [12] GPIO 18  ← BCLK
GPIO 27 [13]  [14] GND
GPIO 22 [15]  [16] GPIO 23
   3.3V [17]  [18] GPIO 24
GPIO 10 [19]  [20] GND
 GPIO 9 [21]  [22] GPIO 25
GPIO 11 [23]  [24] GPIO 8
    GND [25]  [26] GPIO 7
 GPIO 0 [27]  [28] GPIO 1
 GPIO 5 [29]  [30] GND
 GPIO 6 [31]  [32] GPIO 12
GPIO 13 [33]  [34] GND
GPIO 19 [35]  [36] GPIO 16  ← LRC/WS
GPIO 26 [37]  [38] GPIO 20  ← ICS-43434 Data
    GND [39]  [40] GPIO 21  ← MAX98357A Data
```

---

**Last Updated**: 2025-01-27

