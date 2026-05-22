"""
PDF Converter Module
=====================
Converts Word documents to PDF using multiple methods.
"""

import os
import subprocess


try:
    from src.core.config import OUTPUT_DOCX, OUTPUT_PDF
except ImportError:
    OUTPUT_DOCX = "output.docx"
    OUTPUT_PDF = "output.pdf"


def convert_to_pdf(docx_path=None, pdf_path=None):
    """Convert DOCX to PDF using multiple fallback methods."""
    if docx_path is None:
        docx_path = OUTPUT_DOCX
    if pdf_path is None:
        pdf_path = OUTPUT_PDF
    
    print("\n" + "=" * 50)
    print("[CONVERT] Converting DOCX to PDF...")
    print("=" * 50)
    
    if not os.path.exists(docx_path):
        print(f"[ERROR] {docx_path} not found!")
        return False
    
    pdf_success = False
    
    # Method 1: docx2pdf
    if not pdf_success:
        try:
            import docx2pdf
            print("[TRY] Using docx2pdf...")
            docx2pdf.convert(docx_path, pdf_path)
            if os.path.exists(pdf_path):
                pdf_success = True
                print(f"[OK] PDF created: {pdf_path}")
        except ImportError:
            print("[INFO] docx2pdf not installed")
        except Exception as e:
            print(f"[INFO] docx2pdf failed: {e}")
    
    # Method 2: LibreOffice
    if not pdf_success:
        try:
            print("[TRY] Using LibreOffice...")
            subprocess.run(
                ['soffice', '--headless', '--convert-to', 'pdf',
                 '--outdir', os.getcwd(), docx_path],
                capture_output=True, timeout=60
            )
            if os.path.exists(pdf_path):
                pdf_success = True
                print(f"[OK] PDF created via LibreOffice")
        except FileNotFoundError:
            print("[INFO] LibreOffice not found")
        except Exception as e:
            print(f"[INFO] LibreOffice failed: {e}")
    
    # Method 3: Windows Word COM
    if not pdf_success:
        try:
            import win32com.client
            print("[TRY] Using Microsoft Word...")
            word = win32com.client.Dispatch("Word.Application")
            word.Visible = False
            doc = word.Documents.Open(os.path.abspath(docx_path))
            doc.SaveAs(os.path.abspath(pdf_path), FileFormat=17)
            doc.Close()
            word.Quit()
            pdf_success = True
            print(f"[OK] PDF created via Word")
        except ImportError:
            print("[INFO] win32com not available")
        except Exception as e:
            print(f"[INFO] Word conversion failed: {e}")
    
    if pdf_success:
        pdf_size = os.path.getsize(pdf_path)
        print(f"     Size: {pdf_size / 1024:.1f} KB")
    else:
        print("[INFO] PDF conversion not available")
    
    print("=" * 50)
    return pdf_success


def verify_pdf(pdf_path=None):
    """Verify PDF was created."""
    if pdf_path is None:
        pdf_path = OUTPUT_PDF
    
    if os.path.exists(pdf_path):
        size = os.path.getsize(pdf_path)
        print(f"[OK] PDF exists: {pdf_path}")
        print(f"     Size: {size / 1024:.1f} KB")
        return True
    return False


if __name__ == "__main__":
    convert_to_pdf()