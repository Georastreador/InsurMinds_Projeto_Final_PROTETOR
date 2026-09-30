# Golden Dataset Annotation v1.0

Ground Truth manually curated from official Chubb and Sompo D&O contractual-condition PDFs.
Each annotation records expected value, PDF page and a short evidence excerpt.

Important: these are contractual conditions, not issued policy specifications. Missing concrete
policy number, insured entity, dates, monetary limits and retroactive date are deliberate negative
labels, designed to test unsupported inference.

Evaluation policy:
- EVAL-02: compare InsurMinds A3/A4 structured output against annotated fields.
- EVAL-03: verify Claim→Evidence grounding against page/excerpt.
- EVAL-04: compare A5 statuses against the manually labelled comparison matrix.
- No synthetic fixture is accepted as empirical performance evidence.
