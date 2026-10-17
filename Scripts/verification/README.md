# Verification

`verify_october_2026.py` re-derives every claim made about the October work-plan tasks from the files in `Data/`
and writes `Docs/verification/october_2026_checks.csv` and `.md` (PASS / WARN / FAIL / INFO).

```bash
.venv/bin/python Scripts/verification/verify_october_2026.py                    # offline, ~10 s
.venv/bin/python Scripts/verification/verify_october_2026.py --rerun-pipeline   # + re-run the Reddit pipeline on
                                                                                #   both collections and compare
                                                                                #   every table byte-for-byte (~2 min)
.venv/bin/python Scripts/verification/verify_october_2026.py --network          # + re-query Mapillary for 2024-2026
                                                                                #   imagery and refresh the OSM bridge list
```

It exits non-zero only if a Reddit data-integrity check fails. FAILs on imagery and the old placeholder box are
findings about the world, reported in the table, not errors in the data.
