
from generator.resume_screening import save_screening_result

result = save_screening_result(
    requisition_id=1,
    candidate_id=21
)

for key, value in result.items():
    print(f"{key}: {value}")
