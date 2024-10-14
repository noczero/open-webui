import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List

from markdown import markdown
import pdfkit
from starlette.responses import Response

from open_webui.apps.webui.models.chats import ChatTitleMessagesForm
from open_webui.utils.tools import log

log = logging.getLogger(__name__)

class PDFGenerator:
    """
    Description:
    The `PDFGenerator` class is designed to create PDF documents from chat messages.
    The process involves transforming markdown content into HTML and then into a PDF format,
    which can be easily returned as a response to the routes.

    It depends on pdfkit for converting HTML to PDF that uses wkhtmltopdf binary package.

    Attributes:
    - `form_data`: An instance of `ChatTitleMessagesForm` containing title and messages.

    """

    def __init__(self, form_data: ChatTitleMessagesForm):
        self.html_body = None
        self.messages_html = None
        self.form_data = form_data
        self.css_style_file = Path("./backend/open_webui/static/assets/pdf-style.css")

    def build_html_message(self, message: Dict[str, Any]) -> str:
        """Build HTML for a single message."""
        role = message.get("role", "user")
        content = message.get("content", "")
        timestamp = message.get('timestamp')

        model = message.get('model') if role == 'assistant' else ''

        date_str = self.format_timestamp(timestamp) if timestamp else ''

        # extends pymdownx extension to convert markdown to html.
        # - https://facelessuser.github.io/pymdown-extensions/usage_notes/
        html_content = markdown(content, extensions=['pymdownx.extra'])

        html_message = f"""
              <div class="message">
                    <div class="mb-2 mt-4">
                        <div class="d-flex justify-content-between align-items-center">
                            <div>
                              <h2 class="mb-0">
                                <strong>{role.title()}</strong>
                                <small class="text-muted">{model}</small>
                                 <div>
                                    <small class="heading-date">{date_str}</small>
                                </div>
                              </h2>
                            </div>
                        </div>  
                    </div>
                    
                    <div class="markdown-section">
                        {html_content}
                    </div>
                </div>
          """
        return html_message

    def create_pdf_from_html(self) -> bytes:
        """Convert HTML content to PDF and return the bytes."""
        return pdfkit.from_string(self.html_body, output_path=False, css=self.css_style_file)


    def format_timestamp(self, timestamp: float) -> str:
        """Convert a UNIX timestamp to a formatted date string."""
        try:
            date_time = datetime.fromtimestamp(timestamp)
            return date_time.strftime("%Y-%m-%d, %H:%M:%S")
        except (ValueError, TypeError) as e:
            # Log the error if necessary
            return ''

    def generate_chat_pdf(self) -> Response:
        """
        Generate a PDF from chat messages.

        Returns:
            A FastAPI Response with the generated PDF or an error message.
        """
        try:
            # Build HTML messages
            messages_html_list: List[str] = [self.build_html_message(msg) for msg in self.form_data.messages]
            self.messages_html = '<div>' + ''.join(messages_html_list) + '</div>'

            # Generate full HTML body
            self.html_body = self.generate_html_body()

            # Create PDF
            pdf_bytes = self.create_pdf_from_html()

            # Return PDF as response
            return Response(
                content=pdf_bytes,
                media_type="application/pdf",
                headers={"Content-Disposition": "attachment;filename=chat.pdf"},
            )
        except RuntimeError as pdf_error:
            log.error(pdf_error)
            # Handle PDF generation errors
            return Response(content=str(pdf_error), status_code=500)
        except Exception as e:
            # Handle other unexpected errors
            log.error(e)
            return Response(content="An unexpected error occurred.", status_code=500)

    def generate_html_body(self) -> str:
        """Generate the full HTML body for the PDF."""
        return f"""
        <html>
            <head>
                <meta charset="UTF-8">
                <meta name="viewport" content="width=device-width, initial-scale=1.0">
            </head>
            <body>
                <div class="container"> 
                    <div class="text-center">
                        <h1>{self.form_data.title}</h1>
                    </div>
                    <div>
                        {self.messages_html}
                    </div>
                </div>
            </body>
        </html>
        """
