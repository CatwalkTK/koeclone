from fastapi import APIRouter

from koeclone.domain.consent import generate_consent_challenge

router = APIRouter()


@router.get("/consent/challenge")
def get_consent_challenge() -> dict[str, str]:
    return {"consent_text": generate_consent_challenge()}
