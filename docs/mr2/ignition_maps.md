# 17140 ignition maps in degrees

This page comes from `uv run pcmre readable17140 --write` ([`src/pcmre/readable17140.py`](../../src/pcmre/readable17140.py)). Do not edit it by hand.

## Summary

The 17140 has two base ignition maps. Jumper J8 (P34) selects one of them. This page gives each cell in degrees BTDC, for a warm engine with no trims. The rows are manifold pressure in kPa (absolute), on two scales. The columns are engine speed in rpm.

<details>
<summary>Accuracy of the values</summary>

- **Degree scale (CONFIRMED in the simulator):** one map count is 15/64°. The simulator measured this at four engine speeds [EMU:tests/mr2/test_sim17140.py].
- **Absolute degrees (LIKELY):** each cell is value × 15/64° BTDC. The anchor is the T-terminal check. With the throttle closed and T connected to E1, the ROM uses a fixed sum. The factory sets this to 10° BTDC. Warm and with no trims, a map cell is then within 0.04° of its own advance. A warm idle with T open uses the idle table and gives 16.0° BTDC [EMU:tests/mr2/test_ross17140.py::test_t_terminal_fixed_sum_only_with_the_throttle_closed]. Coolant and trim terms add to the value. A timing light at a warm idle with T open must show about 16° ([`maps.md`](maps.md)).
- **kPa scale (two scales, open item):** the LIKELY scale is Load ≈ 6.14 × kPa + 123 (256 counts for 5 V). On this scale the top row is one atmosphere. The simulator default (the first number in each row) is Load ≈ 4.98 × kPa + 98.6. It uses the factory MAP sensor curve and a GUESS converter constant. The Load value at key-on, engine off, decides between them ([open items](../project/open_items.md)).
- High load is at the top of each table, as on a tuning screen. 100 kPa is approximately wide-open throttle at sea level.

</details>

## Map A `$F1EF` (P34 = 1)

| kPa (default / LIKELY) \ rpm | 800 | 1200 | 1600 | 2000 | 2400 | 2800 | 3200 | 3600 | 4000 | 4400 | 4800 | 5200 | 5600 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| **130** / 101 | 5.6 | 11.7 | 12.9 | 15.0 | 18.0 | 18.8 | 17.1 | 17.6 | 16.2 | 19.0 | 20.9 | 23.9 | 26.0 |
| **117** / 91 | 4.0 | 13.6 | 17.3 | 18.3 | 23.4 | 26.7 | 22.5 | 23.9 | 21.6 | 23.9 | 26.2 | 31.4 | 28.6 |
| **104** / 80 | 7.0 | 13.6 | 19.5 | 22.5 | 27.0 | 30.5 | 28.1 | 26.2 | 24.4 | 27.2 | 33.3 | 32.8 | 30.2 |
| **91** / 70 | 17.1 | 22.5 | 25.3 | 26.2 | 31.6 | 31.9 | 33.0 | 35.4 | 34.9 | 36.8 | 38.9 | 38.7 | 37.5 |
| **78** / 60 | 20.2 | 28.1 | 30.2 | 30.5 | 35.6 | 37.0 | 38.0 | 38.0 | 36.6 | 37.5 | 40.1 | 40.5 | 39.6 |
| **66** / 49 | 25.1 | 30.9 | 32.1 | 33.0 | 38.4 | 38.9 | 40.5 | 38.9 | 39.6 | 39.6 | 42.9 | 44.1 | 44.1 |
| **53** / 39 | 31.9 | 34.0 | 40.1 | 38.9 | 41.5 | 46.4 | 48.5 | 47.6 | 45.5 | 46.4 | 49.0 | 47.6 | 49.0 |
| **40** / 28 | 45.0 | 47.1 | 48.0 | 49.0 | 49.5 | 49.9 | 49.9 | 49.9 | 49.9 | 49.0 | 48.5 | 48.5 | 48.5 |

## Map B `$F25D` (P34 = 0)

| kPa (default / LIKELY) \ rpm | 800 | 1200 | 1600 | 2000 | 2400 | 2800 | 3200 | 3600 | 4000 | 4400 | 4800 | 5200 | 5600 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| **130** / 101 | 1.9 | 4.0 | 9.4 | 11.5 | 13.6 | 14.8 | 15.9 | 19.0 | 18.5 | 19.9 | 25.3 | 30.9 | 33.3 |
| **117** / 91 | 4.0 | 8.9 | 12.9 | 16.4 | 18.3 | 20.6 | 19.0 | 20.4 | 20.9 | 23.0 | 28.4 | 32.1 | 33.3 |
| **104** / 80 | 7.7 | 13.1 | 12.4 | 17.1 | 24.8 | 27.9 | 25.5 | 24.4 | 23.0 | 24.8 | 30.0 | 33.0 | 33.5 |
| **91** / 70 | 10.1 | 13.4 | 17.8 | 20.9 | 31.9 | 34.0 | 31.2 | 31.2 | 30.0 | 31.4 | 33.3 | 33.5 | 35.4 |
| **78** / 60 | 21.1 | 27.9 | 30.2 | 32.1 | 35.4 | 35.4 | 35.4 | 35.9 | 35.9 | 37.3 | 38.0 | 38.0 | 38.0 |
| **66** / 49 | 32.6 | 34.5 | 36.1 | 40.5 | 41.0 | 41.5 | 41.5 | 41.7 | 42.0 | 42.7 | 43.6 | 43.6 | 43.6 |
| **53** / 39 | 30.9 | 38.9 | 45.5 | 42.9 | 43.6 | 44.1 | 44.1 | 44.5 | 45.0 | 46.2 | 47.6 | 47.6 | 47.6 |

Between sites the ECU interpolates in both rpm and pressure. Outside the table it holds the edge values.
On a naturally aspirated engine the manifold cannot exceed about 100 kPa. On the LIKELY scale the top row of both maps is one atmosphere (101 kPa), so every row is used. On the simulator default the 117 and 130 kPa rows would never be reached, which is one reason that scale is doubted (maps.md).
