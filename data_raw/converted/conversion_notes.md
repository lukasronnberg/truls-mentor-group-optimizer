# Converted Import Notes

Outputs:

- `scenario.json`
- `mentors.csv`
- `blocked_pairs.csv`

Assumptions applied:

- all genders were left as `unknown`; no gender inference was performed from names
- `gender_review.csv` was generated for manual completion
- `Tema` -> period 1
- `Uppdrag` -> period 2
- `Axel Arlehov` -> `Axel Sjöqvist Arlehov`
- `Freja Linusson Hahn (...)` -> `Freja Linusson-Hahn`
- stray `T` row in the two-period column was ignored
- duplicate `Lukas Doberhof` entry in the `SexI` column was deduplicated
- `PeppI` and `GrillI` were ignored
- no blocked pairs were available in the raw data, so export is empty
- `gender` was not present in the workbooks and was set to `unknown` for everyone

Counts:

- total mentors: 137
- hovding: 20
- normal one-period: 40
- normal two-period: 53
- sexi: 24

Unresolved items:

- No application row found for Axel Sjöqvist Arlehov (phadder_one_period).
