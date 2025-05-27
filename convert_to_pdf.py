import os
import subprocess
import tempfile

def convert_to_pdf_pandoc(input_path: str, output_dir: str, input_format: str = "docx") -> str:
    """Converts a document to PDF using Pandoc.
    Returns the path to the converted PDF file.
    Raises Exception if conversion fails.
    """
    os.makedirs(output_dir, exist_ok=True)
    base_name = os.path.splitext(os.path.basename(input_path))[0]
    pdf_filename = os.path.join(output_dir, f"{base_name}.pdf")

    # Check if pandoc command is available
    try:
        subprocess.run(["pandoc", "--version"], check=True, capture_output=True)
    except (subprocess.CalledProcessError, FileNotFoundError):
        raise RuntimeError("Pandoc command not found or not executable. Please ensure Pandoc is installed and in PATH.")

    cmd = [
        "pandoc",
        input_path,
        "-f", input_format, # Specify input format
        "-t", "pdf",       # Specify output format
        "-o", pdf_filename
    ]
    # For better PDF output, Pandoc often uses a LaTeX engine by default (e.g., pdflatex).
    # Ensure a LaTeX distribution is installed if you need high-quality PDF output,
    # or specify a different PDF engine if available and simpler (e.g., --pdf-engine=weasyprint, if pandoc supports it and weasyprint is installed)
    # cmd.extend(["--pdf-engine=pdflatex"]) # Example

    process = subprocess.run(cmd, capture_output=True, text=True, timeout=120) # 2 min timeout

    if process.returncode != 0:
        error_message = f"Pandoc conversion failed for {input_path}. Error: {process.stderr} Output: {process.stdout}"
        print(error_message) # Log for debugging
        raise Exception(error_message)

    if not os.path.exists(pdf_filename):
        raise Exception(f"Pandoc conversion seemed to succeed but PDF file {pdf_filename} not found.")
            
    return pdf_filename


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