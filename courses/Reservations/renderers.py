from rest_framework import renderers
from weasyprint import HTML
from io import BytesIO

class WeasyPrintPDFRenderer(renderers.BaseRenderer):
    media_type = 'application/pdf'
    format = 'pdf'
    charset = None
    render_style = 'binary'

    def render(self, data, media_type=None, renderer_context=None):
        # Récupérer le HTML à partir des données
        html_string = data.get('html_string')
        if not html_string:
            raise ValueError("Le champ 'html_string' est requis dans les données.")

        # Convertir le HTML en PDF avec WeasyPrint
        pdf_buffer = BytesIO()
        HTML(string=html_string).write_pdf(pdf_buffer)
        pdf_buffer.seek(0)

        # Retourner le contenu du PDF
        return pdf_buffer.getvalue()