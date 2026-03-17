# Raw Data Review Notes

Source files reviewed:

- `data_raw/RESULTAT.xlsx`
- `data_raw/Phadder & GrillI ansökan.xlsx`
- `data_raw/PeppI & Høvding ansökan.xlsx`

Ignored on purpose:

- `PeppI`
- `GrillI`

## Working Assumptions

- `Tema` = period 1
- `Uppdrag` = period 2

## Counts Seen In `RESULTAT.xlsx`

- Høvding selected: 20
- One-period phadder selected: 40
- Two-period phadder selected: 54 entries, but one entry is a stray `T` and is not a person
- SexI selected: 25

Likely intended real count for two-period phadders: 53

## Important Domain Mismatch

The current application is configured for:

- 40 one-period normal mentors total
- 83 two-period normal mentors total
  - `8 * 10 groups + 3 extra in international`

The `RESULTAT.xlsx` sheet instead appears to target:

- 40 one-period phadders total
- 53 two-period phadders total
  - the header literally says `5*10 + 3 extra i intis`

So the raw selection data does **not** match the current solver quota for two-period normal mentors.

This means one of these must be true before final import:

- the real quota should be `5` two-period normal mentors per group, not `8`
- or `RESULTAT.xlsx` is incomplete relative to the current app model

## Clear Fixes Needed

These look like spelling or formatting mismatches and should be normalized before import:

- `Freja Linusson Hahn` -> likely `Freja Linusson-Hahn`
- `Albert Ahnfeldt` -> likely `Albert Ahnfelt`
- `Ana Corloka` -> likely `Ana Corluka`
- `Martin Petterson` -> likely `Martin Pettersson`
- `Jakob Shishoo` -> likely `Jacob Shishoo`
- `Ingrid Wjikström` -> likely `Ingrid Wijkström`
- `Erik Svedman` -> likely `Erik Svedman Sundberg`
- `Ana Garcia` -> likely `Ana Garcia Andersson`
- `Harald Lidén Ulvskog - Event` -> likely `Harald Lidén Ulvskog` with event marker stored separately

## Needs Manual Confirmation

- `Axel Arlehov`
  - I could not find a clean application row with this exact selected name.
  - Strong clue from wishes suggests this may be `Axel Sjöqvist Arlehov`.
  - Please confirm the exact full name.

- `Freja Linusson Hahn (intis) (bollplank tema, høvding vanlig grupp)`
  - The person matches well to `Freja Linusson-Hahn`.
  - The extra notes in parentheses should not be treated as part of the name.
  - Please confirm whether:
    - `intis` should be imported as international preference
    - `bollplank tema` should be ignored for the optimizer

## Broken Cell In `RESULTAT`

- `RESULTAT.xlsx` -> `Blad1` -> row 69 -> two-period phadder column
- The cell contains only `T`
- This is not a person and should be removed or replaced with the intended name

## Data Mapping Notes

- In the local phadder sheet:
  - `1.0` with `Tema` means one-period, preferred period 1
  - `1.0` with `Uppdrag` means one-period, preferred period 2
  - `2.0` means two-period
- In the English phadder sheet:
  - `Theme Phadder` maps to preferred period 1
  - `Mission Phadder` maps to preferred period 2
  - `4.0` maps to two-period
  - `2.0` maps to one-period
- `Intis` / `intis-phadder` / `(intis)` markers appear in result labels and should likely map to international preference
- `(Event)` markers in `RESULTAT` should map to normal subrole `event`, not stay inside the name
