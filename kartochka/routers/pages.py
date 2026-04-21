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


@router.get("/billing", response_class=HTMLResponse)
async def billing_page(request: Request) -> HTMLResponse:
    return templates.TemplateResponse("billing.html", {"request": request})


@router.get("/billing/upgrade", response_class=HTMLResponse)
async def billing_upgrade_page(request: Request) -> HTMLResponse:
    return templates.TemplateResponse("pricing.html", {"request": request})


@router.get("/pricing", response_class=HTMLResponse)
async def pricing_page(request: Request) -> HTMLResponse:
    return templates.TemplateResponse("pricing.html", {"request": request})


@router.get("/marketplace/connect", response_class=HTMLResponse)
async def marketplace_connect_page(request: Request) -> HTMLResponse:
    return templates.TemplateResponse("marketplace_connect.html", {"request": request})


@router.get("/catalog/upload", response_class=HTMLResponse)
async def catalog_upload_page(request: Request) -> HTMLResponse:
    return templates.TemplateResponse("catalog_upload.html", {"request": request})


@router.get("/catalog/batches", response_class=HTMLResponse)
async def catalog_batches_page(request: Request) -> HTMLResponse:
    return templates.TemplateResponse("catalog_batches.html", {"request": request})


@router.get("/catalog/batches/{uid}", response_class=HTMLResponse)
async def catalog_batch_page(uid: str, request: Request) -> HTMLResponse:
    return templates.TemplateResponse(
        "catalog_batch.html", {"request": request, "batch_uid": uid}
    )


@router.get("/settings", response_class=HTMLResponse)
async def settings_page(request: Request) -> HTMLResponse:
    return templates.TemplateResponse("settings.html", {"request": request})


@router.get("/onboarding", response_class=HTMLResponse)
async def onboarding_page(request: Request) -> HTMLResponse:
    return templates.TemplateResponse("onboarding.html", {"request": request})
