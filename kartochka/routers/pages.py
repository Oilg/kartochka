from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

router = APIRouter(tags=["pages"])

templates = Jinja2Templates(directory="templates")


@router.get("/", response_class=RedirectResponse)
async def index() -> RedirectResponse:
    return RedirectResponse(url="/dashboard", status_code=302)


@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request) -> HTMLResponse:
    return templates.TemplateResponse("login.html", {"request": request})


@router.get("/register", response_class=HTMLResponse)
async def register_page(request: Request) -> HTMLResponse:
    return templates.TemplateResponse("register.html", {"request": request})


@router.get("/dashboard", response_class=HTMLResponse)
async def dashboard_page(request: Request) -> HTMLResponse:
    return templates.TemplateResponse("dashboard.html", {"request": request})


@router.get("/templates", response_class=HTMLResponse)
async def templates_list_page(request: Request) -> HTMLResponse:
    return templates.TemplateResponse("templates_list.html", {"request": request})


@router.get("/editor", response_class=HTMLResponse)
async def editor_page(request: Request) -> HTMLResponse:
    return templates.TemplateResponse("editor.html", {"request": request})


@router.get("/editor/{uid}", response_class=HTMLResponse)
async def editor_uid_page(uid: str, request: Request) -> HTMLResponse:
    return templates.TemplateResponse(
        "editor.html", {"request": request, "template_uid": uid}
    )


@router.get("/generate", response_class=HTMLResponse)
async def generate_page(request: Request) -> HTMLResponse:
    return templates.TemplateResponse("generation_new.html", {"request": request})


@router.get("/generate/{uid}", response_class=HTMLResponse)
async def generate_uid_page(uid: str, request: Request) -> HTMLResponse:
    return templates.TemplateResponse(
        "generation_new.html", {"request": request, "template_uid": uid}
    )


@router.get("/generations/{uid}", response_class=HTMLResponse)
async def generation_result_page(uid: str, request: Request) -> HTMLResponse:
    return templates.TemplateResponse(
        "generation_result.html", {"request": request, "generation_uid": uid}
    )


@router.get("/api-docs", response_class=HTMLResponse)
async def api_docs_page(request: Request) -> HTMLResponse:
    return templates.TemplateResponse("api_docs.html", {"request": request})
