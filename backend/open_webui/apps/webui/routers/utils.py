from datetime import datetime
from io import BytesIO
from pathlib import Path
from textwrap import dedent
import black
import markdown
from fastapi.staticfiles import StaticFiles
from xhtml2pdf import pisa

from open_webui.config import DATA_DIR, ENABLE_ADMIN_EXPORT
from open_webui.constants import ERROR_MESSAGES
from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel
from starlette.responses import FileResponse
from open_webui.utils.misc import get_gravatar_url
from open_webui.utils.utils import get_admin_user

router = APIRouter()


@router.get("/gravatar")
async def get_gravatar(
    email: str,
):
    return get_gravatar_url(email)


class CodeFormatRequest(BaseModel):
    code: str


@router.post("/code/format")
async def format_code(request: CodeFormatRequest):
    try:
        formatted_code = black.format_str(request.code, mode=black.Mode())
        return {"code": formatted_code}
    except black.NothingChanged:
        return {"code": request.code}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


class MarkdownForm(BaseModel):
    md: str


@router.post("/markdown")
async def get_html_from_markdown(
    form_data: MarkdownForm,
):
    return {"html": markdown.markdown(form_data.md)}


class ChatForm(BaseModel):
    title: str
    messages: list[dict]


@router.post("/pdf")
async def download_chat_as_pdf(
    form_data: ChatForm,
):
    html_messages = '<div>'

    # Add chat messages
    for message in form_data.messages:
        role = message["role"]
        content = message["content"]

        if message.get('timestamp',None):
            date_time = datetime.fromtimestamp(message['timestamp'])
            date_str = date_time.strftime("%Y-%m-%d, %H:%M:%S")
        else:
            date_str = ''

        model = message['model'] if role == 'assistant' else ''
        html_content = markdown.markdown(
            content, extensions=['pymdownx.extra']
        )
        html_message = f"""
                <div class="message">
                    <small>{date_str}</small>
                    <div>
                      <h2>
                        <strong>{role.title()}</strong>
                        <small class="text-muted">{model}</small>
                      </h2>
                    </div>
                    
                    <div class="markdown-section">
                        {html_content}
                    </div>
                </div>
            """

        html_messages += html_message

    html_messages += "</div>"

    css_style_file = Path("./backend/open_webui/static/assets/pdf-style.css")

    html_body = dedent(
        f"""
            <html>
                <meta charset="UTF-8">
                <meta name="viewport" content="width=device-width, initial-scale=1.0">
                <link rel="stylesheet" href="{css_style_file}">
                <body>
                    <div class="container"> 
                        <div class="text-center">
                            <h1> 
                                {form_data.title}
                            </h1>
                        </div>
                        <div>
                            {html_messages}
                        </div>
                    </div>
                </body>
            </html>
        """
    )


    pdf_buffer = BytesIO()
    pisa_status = pisa.CreatePDF(html_body, dest=pdf_buffer)

    if pisa_status.err:
        return Response(content="Error generating PDF", status_code=500)

    pdf_bytes = pdf_buffer.getvalue()

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": "attachment;filename=chat.pdf"},
    )


@router.get("/db/download")
async def download_db(user=Depends(get_admin_user)):
    if not ENABLE_ADMIN_EXPORT:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=ERROR_MESSAGES.ACCESS_PROHIBITED,
        )
    from open_webui.apps.webui.internal.db import engine

    if engine.name != "sqlite":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=ERROR_MESSAGES.DB_NOT_SQLITE,
        )
    return FileResponse(
        engine.url.database,
        media_type="application/octet-stream",
        filename="webui.db",
    )


@router.get("/litellm/config")
async def download_litellm_config_yaml(user=Depends(get_admin_user)):
    return FileResponse(
        f"{DATA_DIR}/litellm/config.yaml",
        media_type="application/octet-stream",
        filename="config.yaml",
    )
