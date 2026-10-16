// In-car test rig pin map (docs/procedures/car_test.md): the Pico 2 W in place of
// the D151801, one female-to-male jumper per signal from its header to a spare DIP-40 socket in the
// ECU's CPU socket. For the car firmware (still to write); parsed and checked by
// src/pcmre/car_rig_diagram.py, which generates the wire table and the wiring picture.
//
// Direction is the CPU's, as the 17140 ROM sets it [ROM:$F2CA-$F2EB reset, $F371-$F380 every main-loop
// pass] CONFIRMED (code):
//   DDR1 = $3E: P11-P15 out, P10/P16/P17 in.   DDR2 = $F2 at reset, $FE in the main loop: P21/P24 out,
//   P20 in, P22/P23 in at reset then out (P23 is the SCI's RX when the link is on: IO).
//   DDR3 = $02: P31 out, the rest in.           DDR4 = $03: P40/P41 out (P42-P47 are straps, no wire).
//
// The rule: GP0-22 take 5 V (only while the Pico is powered); GP26-28 do not. So GP26-28 carry only
// pins the ROM always drives as outputs, P12-P14 (the ADC channel select), which nothing on the ECU
// board can drive. Every pin the ECU board can drive (IN, IO, /RES) is on GP0-22. Unlike the chip test
// (chipdiff.h), NE/IDL/P17 sit on GP15-17 and P12-P14 on GP26-28, and EXTAL (GP9) has no wire: the
// ECU's crystal stays unused.
//
// GPIO, port, bit, direction (port 0 = the IS3 strobe on SC1).

#ifndef CAR_PINS_H
#define CAR_PINS_H

#define CAR_PINS(X)                                                                                                    \
    X(0, 3, 0, IN)    /* P30  T terminal       pin 37 */                                                               \
    X(1, 3, 1, OUT)   /* P31                   pin 36 */                                                               \
    X(2, 3, 2, IN)    /* P32                   pin 35 */                                                               \
    X(3, 3, 3, IN)    /* P33                   pin 34 */                                                               \
    X(4, 3, 4, IN)    /* P34  J8               pin 33 */                                                               \
    X(5, 3, 5, IN)    /* P35  G                pin 32 */                                                               \
    X(6, 1, 5, OUT)   /* P15  ADC hold         pin 18 */                                                               \
    X(7, 3, 7, IN)    /* P37                   pin 30 */                                                               \
    X(10, 4, 0, OUT)  /* P40                   pin 29 */                                                               \
    X(11, 4, 1, OUT)  /* P41                   pin 28 */                                                               \
    X(12, 2, 0, IN)   /* P20  ADC end          pin 8  */                                                               \
    X(13, 2, 1, OUT)  /* P21  injector         pin 9  */                                                               \
    X(14, 1, 1, OUT)  /* P11  IGT              pin 14 */                                                               \
    X(15, 1, 0, IN)   /* P10  NE               pin 13 */                                                               \
    X(16, 1, 6, IN)   /* P16  IDL              pin 19 */                                                               \
    X(17, 1, 7, IN)   /* P17                   pin 20 */                                                               \
    X(18, 0, 0, IN)   /* SC1  IS3 / IGF        pin 39 */                                                               \
    X(20, 2, 2, IO)   /* P22                   pin 10 */                                                               \
    X(21, 2, 4, OUT)  /* P24  TX / fault lamp  pin 12 */                                                               \
    X(22, 2, 3, IO)   /* P23  RX               pin 11 */                                                               \
    X(26, 1, 2, OUT)  /* P12  ADC select       pin 15 */                                                               \
    X(27, 1, 3, OUT)  /* P13  ADC select       pin 16 */                                                               \
    X(28, 1, 4, OUT)  /* P14  ADC select       pin 17 */

#define CAR_GPIO_RES 8u  // /RES, pin 6: from the ECU's reset circuit (input)
#define CAR_GPIO_E 19u   // E, pin 40: driven at 1 MHz
#define CAR_GND_PICO_PIN 3  // a Pico GND pin, to CPU pin 1 (Vss)

#define CAR_ADC_SEL_SHIFT 26  // P12-P14 on GP26-28: the channel number

#define CAR_DIR_IN 1
#define CAR_DIR_IO 1
#define CAR_DIR_OUT 0
#define CAR_DRIVEN_(g, port, bit, dir) | (CAR_DIR_##dir ? (1u << (g)) : 0u)
// Pins the ECU board can drive: CPU inputs, the two pins the ROM turns round, and /RES
#define CAR_DRIVEN_MASK ((0u CAR_PINS(CAR_DRIVEN_)) | (1u << CAR_GPIO_RES))
#define CAR_5V_TOLERANT 0x007FFFFFu  // GP0-22

_Static_assert((CAR_DRIVEN_MASK & ~CAR_5V_TOLERANT) == 0, "a pin the ECU can drive is on a GPIO that is not 5 V tolerant");

#endif
