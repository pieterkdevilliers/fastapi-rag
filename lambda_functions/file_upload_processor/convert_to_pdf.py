import os
import subprocess
import tempfile
import shutil
from weasyprint import HTML, CSS
from markdown_it import MarkdownIt
import pandas as pd

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


def convert_doc_to_docx_libreoffice(input_doc_path: str, output_dir: str) -> str:
    """
    Converts a .doc file to a .docx file using the definitive "HOME=/tmp" strategy
    and trusting the existence of the output file over the process exit code, which
    can be non-zero even on success due to benign warnings (e.g., missing Java).
    """
    temp_env = os.environ.copy()
    temp_env['HOME'] = '/tmp'

    cmd = [
        "libreoffice",
        "--headless",
        "--invisible",
        "--nologo",
        "--norestore",
        "--convert-to", "docx",
        "--outdir", output_dir,
        input_doc_path
    ]

    # Run the conversion process
    process = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=180,
        env=temp_env
    )

    # Calculate the expected output path
    base_name = os.path.splitext(os.path.basename(input_doc_path))[0]
    output_docx_path = os.path.join(output_dir, f"{base_name}.docx")

    # --- THIS IS THE FINAL, CRITICAL LOGIC ---
    # The primary proof of success is the existence of the output file.
    if not os.path.exists(output_docx_path):
        # If the file was NOT created, then it was a true failure. Raise the error.
        error_message = (
            f"LibreOffice conversion failed for {input_doc_path}. "
            f"Output file not found. Exit Code: {process.returncode}. "
            f"Stderr: {process.stderr}"
        )
        raise Exception(error_message)

    # If the file WAS created, we can consider it a success.
    # We can log any warnings from stderr for debugging, but we don't treat it as an error.
    if process.returncode != 0:
        print(f"INFO: LibreOffice conversion for {input_doc_path} succeeded, "
              f"but exited with a non-zero status code (likely due to warnings). "
              f"Stderr: {process.stderr}")

    return output_docx_path


def convert_text_to_pdf(text_content: str):
    """Converts plain text to a simple PDF."""
    # A very basic HTML wrapper for text to make it look reasonable in PDF
    html_content = f"""
    <html>
      <head><meta charset="UTF-8"></head>
      <body><pre style="white-space: pre-wrap; word-wrap: break-word; font-family: monospace;">{text_content}</pre></body>
    </html>
    """
        # WeasyPrint can write directly to a byte string
    try:
        pdf_bytes = HTML(string=html_content).write_pdf()
        if not pdf_bytes:
            raise ValueError("WeasyPrint returned empty PDF bytes.")
        return pdf_bytes
    except Exception as e:
        print(f"Error during PDF conversion with WeasyPrint: {e}")
        # Re-raise as a standard exception that the Lambda handler can catch
        raise ValueError(f"Failed to convert text to PDF: {e}") from e


def convert_markdown_to_pdf(md_content: str, output_path: str):
    """Converts Markdown to PDF."""
    md = MarkdownIt()
    html_content = md.render(md_content)
    # Add basic HTML structure if not already present from markdown rendering for WeasyPrint
    full_html = f"<html><head><meta charset='UTF-8'></head><body>{html_content}</body></html>"
    HTML(string=full_html).write_pdf(output_path)


def convert_excel_to_pdf_bytes(input_excel_path: str) -> bytes:
    """
    Reads an Excel file (.xls or .xlsx), converts each sheet to a styled
    HTML table, and renders the result as PDF bytes using WeasyPrint.

    :param input_excel_path: The local file path to the downloaded Excel file.
    :return: The content of the generated PDF as a bytes object.
    """
    try:
        xls = pd.ExcelFile(input_excel_path)
    except Exception as e:
        raise ValueError(f"Failed to read Excel file. It may be corrupt or an unsupported format. Error: {e}")

    # Start building the HTML document in memory
    html_parts = [
        "<html><head><title>Spreadsheet</title><style>",
        "body { font-family: sans-serif; }",
        # Style for tables to make them look clean and readable
        "table { border-collapse: collapse; width: 100%; margin-bottom: 25px; font-size: 10pt; }",
        "th, td { border: 1px solid #cccccc; padding: 6px; text-align: left; word-wrap: break-word; max-width: 250px; }",
        "th { background-color: #f2f2f2; font-weight: bold; }",
        # Style for sheet titles, ensuring each new sheet starts on a new page
        "h1 { font-size: 16pt; page-break-before: always; }",
        # Prevent a page break before the very first sheet
        "h1:first-of-type { page-break-before: auto; }",
        "</style></head><body>"
    ]

    if not xls.sheet_names:
        raise ValueError("The provided Excel file has no sheets.")

    # Iterate over each sheet in the Excel file
    for sheet_name in xls.sheet_names:
        df = pd.read_excel(xls, sheet_name=sheet_name)
        # Skip empty sheets
        if df.empty:
            continue
        
        # Add a title for the sheet
        html_parts.append(f"<h1>Sheet: {sheet_name}</h1>")
        # Convert the pandas DataFrame to an HTML table string
        # index=False prevents writing the pandas index
        # na_rep='' replaces NaN values with an empty string for a cleaner look
        html_parts.append(df.to_html(index=False, na_rep=''))

    html_parts.append("</body></html>")
    full_html_string = "".join(html_parts)

    # Use WeasyPrint to convert the final HTML string to PDF bytes directly
    try:
        pdf_bytes = HTML(string=full_html_string).write_pdf()
        if not pdf_bytes:
            raise ValueError("WeasyPrint returned empty PDF bytes from Excel conversion.")
        return pdf_bytes
    except Exception as e:
        # Catch potential WeasyPrint errors
        raise Exception(f"WeasyPrint failed to render PDF from Excel-generated HTML. Error: {e}")