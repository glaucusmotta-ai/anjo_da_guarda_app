from fastapi import APIRouter
from fastapi.responses import RedirectResponse

router = APIRouter()

@router.get("/central/login")
def central_login_alias():
    return RedirectResponse(url="/central", status_code=302)
