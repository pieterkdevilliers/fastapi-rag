import os
import subprocess
import tempfile
from weasyprint import HTML, CSS
from weasyprint.fonts import FontConfiguration

def convert_to_html_pandoc(input_path: str, output_dir: str, input_format: str = "docx") -> str:
    """Converts a document to HTML using Pandoc.
    Returns the path to the converted HTML file.
    Raises Exception if conversion fails.
    """
    os.makedirs(output_dir, exist_ok=True)
    base_name = os.path.splitext(os.path.basename(input_path))[0]
    html_filename = os.path.join(output_dir, f"{base_name}.html")

    # Check if pandoc command is available
    try:
        subprocess.run(["pandoc", "--version"], check=True, capture_output=True)
    except (subprocess.CalledProcessError, FileNotFoundError):
        raise RuntimeError("Pandoc command not found or not executable. Please ensure Pandoc is installed and in PATH.")

    cmd = [
        "pandoc",
        input_path,
        "-f", input_format, # Specify input format
        "-t", "html5",       # Specify output format
        "-o", html_filename
    ]

    process = subprocess.run(cmd, capture_output=True, text=True, timeout=120) # 2 min timeout

    if process.returncode != 0:
        error_message = f"Pandoc conversion failed for {input_path}. Error: {process.stderr} Output: {process.stdout}"
        print(error_message) # Log for debugging
        raise Exception(error_message)

    if not os.path.exists(html_filename):
        raise Exception(f"Pandoc conversion seemed to succeed but HTML file {html_filename} not found.")
            
    return html_filename


def convert_html_to_pdf_weasyprint(html_input: str, output_pdf_path: str, is_file_path: bool = False):
    """
    Converts HTML content or an HTML file to a PDF file using WeasyPrint.

    :param html_input: HTML content as a string OR path to an HTML file.
    :param output_pdf_path: The full path where the output PDF should be saved.
    :param is_file_path: Set to True if html_input is a file path, False if it's an HTML string.
    """
    try:
        # font_config = FontConfiguration() # Optional: for custom font configurations
        # css = CSS(string='@page { size: A4; margin: 2cm }', font_config=font_config) # Example CSS

        if is_file_path:
            HTML(filename=html_input).write_pdf(output_pdf_path) #, stylesheets=[css])
        else:
            # Ensure the HTML string is properly encoded for WeasyPrint if necessary
            # Pandoc usually outputs UTF-8, which should be fine.
            HTML(string=html_input).write_pdf(output_pdf_path) #, stylesheets=[css])
        
        if not os.path.exists(output_pdf_path):
            raise Exception(f"WeasyPrint conversion: PDF file {output_pdf_path} was not created.")

    except Exception as e:
        error_message = f"WeasyPrint HTML to PDF conversion failed for input. Error: {str(e)}"
        print(error_message) # Log for debugging
        raise Exception(error_message) # Re-raise to be caught by the calling function


def convert_text_to_pdf(text_content: str, output_path: str):
    """Converts plain text to a simple PDF."""
    # A very basic HTML wrapper for text to make it look reasonable in PDF
    html_content = f"""
    <html>
      <head><meta charset="UTF-8"></head>
      <body><pre style="white-space: pre-wrap; word-wrap: break-word; font-family: monospace;">{text_content}</pre></body>
    </html>
    """
    HTML(string=html_content).write_pdf(output_path)


def convert_markdown_to_pdf(md_content: str, output_path: str):
    """Converts Markdown to PDF."""
    md = MarkdownIt()
    html_content = md.render(md_content)
    # Add basic HTML structure if not already present from markdown rendering for WeasyPrint
    full_html = f"<html><head><meta charset='UTF-8'></head><body>{html_content}</body></html>"
    HTML(string=full_html).write_pdf(output_path)