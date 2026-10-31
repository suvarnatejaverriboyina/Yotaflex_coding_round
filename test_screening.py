
from generator.resume_screening import screen_candidate

result = screen_candidate(
    requisition_id=1,
    candidate_id=21
)

for key, value in result.items():
    print(f"{key}: {value}")
