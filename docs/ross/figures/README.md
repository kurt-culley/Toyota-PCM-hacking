# Ross figures

## Summary

This folder holds the 16 images of the Ross PDF (*Lifting the Lid on the mk1 MR2 ECU*) and the data read from their graphs. The command `uv run pcmre digitise` ([`digitise.py`](../../../src/pcmre/ross/digitise.py)) makes all the PNG and CSV files. Do not edit them by hand. The data shows the **17030** (mk1a) ECU, not ROM data, so its evidence level is `[PDF]`. The [claim register](../claims.md) compares it with the 17140 and the Bluetop ROMs.

<details>
<summary>How the files are made</summary>

- The PDF stores each image upside down. The script turns them upright.
- The script reads the graph data from the pixels. Each CSV gives its source page, its claims and its resolution in its header.
- [`tests/mr2/test_ross_figures.py`](../../../tests/mr2/test_ross_figures.py) examines the files.

</details>

## Figures

| Image | Page | Content | Data | Claims |
|---|---|---|---|---|
| [img00](img00.png) | p4 | Density map: EFI value vs MAP site, <3200 and >3200 rpm | [p04_density_map.csv](p04_density_map.csv) | R-F03, R-F05 |
| [img01](img01.png) | p5 | Speed correction >3200 rpm | [p05_speed_corr_above_3200.csv](p05_speed_corr_above_3200.csv) | R-F07 |
| [img02](img02.png) | p5 | Speed correction <3200 rpm | [p05_speed_corr_below_3200.csv](p05_speed_corr_below_3200.csv) | R-F08 |
| [img03](img03.png) | p6 | Hard-driving fuel correction | [p06_hard_driving_corr.csv](p06_hard_driving_corr.csv) | R-F09, R-F10 |
| [img04](img04.png) | p6 | Air temperature (THA) correction | [p06_air_temp_corr.csv](p06_air_temp_corr.csv) | R-F11 |
| [img05](img05.png) | p7 | Injector response (dead time) vs battery voltage | [p07_injector_dead_time.csv](p07_injector_dead_time.csv) | R-F17 |
| [img06](img06.png) | p8 | Ross's emulator output, EFI value vs rpm for each MAP site | qualitative | R-F18 |
| [img07](img07.png) | p8 | Datalog from a real car (throttle enrichment, T-VIS, ignition trace) | qualitative | R-F18 |
| [img08](img08.png) | p9 | Toyota manual excerpt: simultaneous injection timing | qualitative (not Ross's own data) | R-F23 |
| [img09](img09.png) | p12 | **17×8 ignition table, raw 8-bit** | [p12_ignition_table_17030_raw.csv](p12_ignition_table_17030_raw.csv) (transcribed) | R-I02–R-I04 |
| [img10](img10.png) | p13 | The same table drawn as one line per MAP site | used to check the transcription | R-I02 |
| [img11](img11.png) | p14 | The same table as a 3D surface | qualitative | R-I05 |
| [img12](img12.png) | p14 | Idle/overrun ignition map, raw | [p14_idle_overrun_ignition.csv](p14_idle_overrun_ignition.csv) | R-I07 |
| [img13](img13.png) | p16 | Overall advance in degrees BTDC (3D) | qualitative; the conversion is disputed | R-I06 |
| [img14](img14.png) | p17 | Mixture-screw rpm correction MX2 (17030 and 17140) | [p17_mixture_rpm_corr.csv](p17_mixture_rpm_corr.csv) | R-M02 |
| [img15](img15.png) | p18 | Photo of the mixture screw at its zero position (89661-17140) | qualitative | R-M07 |

## Checks

- **The ignition table agrees with the Ross chart.** MAP 1, MAP 2 and the low band of MAP 8 agree with the p13 line chart. The difference is 1 count or less at each rpm site. The cells at MAP 8, 2000–4000 rpm, read 81 and 85, not 61 and 65 [EMU:test_ross_figures.py::test_ignition_table_matches_p13_chart].
- **The mixture correction agrees with the Ross text:** 128 at 1000 rpm and 64 at 3600 rpm [EMU:test_ross_figures.py::test_mixture_correction_matches_ross_text].
- **Resolution:** the readings are correct to about ±1 pixel. Each CSV header gives this in data units (for example ±0.9 EFI units on the density map and ±6.9 µs on the dead-time curve).

## Observations

- **The <3200 rpm speed-correction points are not at equal rpm steps.**
  - They are at about 533, 800, 1067, 1333, 1600, 2000, 2400, 2800 and 3200 rpm.
  - Thus the step is 267 rpm below 1600 rpm and 400 rpm above it.
  - The 17140 table `$F1AE` also has closer sites at low rpm (R-F08).
- **Idle and closed-throttle ignition:** a flat 68 (raw) up to 1200 rpm, up to 162 at about 2000 rpm, then flat. The 17140 idle table has the same values (R-I07). This ignition applies while the throttle is closed. Thus it controls the idle when there is no IACV air.
- **Dead time:** it decreases from about 1410 µs at 7 V to 270 µs at 16.5 V.

### In tuning terms

The density map is the base fuel against load (MAP site). The speed tables are a volumetric-efficiency trim against rpm: −15 % to +11 % below 3200 rpm and −10 % to +7 % above. The hard-driving and air-temperature corrections multiply the result. The ignition table is a conventional map of 17 rpm × 8 load sites. Higher raw values give more advance, and the Ross degrees chart (p16) has the same shape. The advance decreases when the cylinder filling increases. The conversion from raw to degrees is open (R-I06).
