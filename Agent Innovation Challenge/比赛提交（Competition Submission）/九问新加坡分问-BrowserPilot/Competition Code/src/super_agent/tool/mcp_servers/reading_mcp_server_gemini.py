import argparse
import os
import tempfile
import requests
import atexit
import io
import time
import logging
import pathlib
from PyPDF2 import PdfReader

from fastmcp import FastMCP
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
import asyncio
from .utils.smart_request import smart_request
from .utils.downloader import download_pdf_with_selenium
from google import genai
from google.genai import types

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('mcp_logs/reading_mcp_server_gemini.log')
    ]
)
logger = logging.getLogger('reading_mcp_server_gemini')

# Initialize FastMCP server

mcp = FastMCP("reading-mcp-server")

# Initialize Gemini client
GOOGLE_API_KEY = os.environ.get("GEMINI_API_KEY", "")
if GOOGLE_API_KEY:
    gemini_client = genai.Client(api_key=GOOGLE_API_KEY)
else:
    gemini_client = None

# PDF processing limits for Gemini
MAX_PDF_SIZE_BYTES = 0.1 * 1024 * 1024  # 20 MB for direct Gemini processing (use File API for larger)
MAX_PDF_SIZE_FILE_API = 50 * 1024 * 1024  # 50 MB max for File API
MAX_PDF_PAGES = 1000  # 1000 pages for Gemini


async def get_pdf_info(pdf_data: bytes) -> tuple[int, int]:
    """
    Get PDF file size and page count.
    
    Args:
        pdf_data: Raw PDF data as bytes
        
    Returns:
        Tuple of (file_size_bytes, page_count)
    """
    try:
        file_size = len(pdf_data)
        
        # Create PDF reader from bytes
        pdf_stream = io.BytesIO(pdf_data)
        pdf_reader = PdfReader(pdf_stream)
        page_count = len(pdf_reader.pages)
        
        return file_size, page_count
    except Exception as e:
        # If we can't read the PDF, assume it's large to be safe
        logger.warning(f"Failed to get PDF info: {e}")
        return len(pdf_data), 9999


async def process_with_markitdown(pdf_path: str) -> str:
    """
    Process PDF with markitdown-mcp server to convert to markdown.
    
    Args:
        pdf_path: Path to the PDF file
        
    Returns:
        Markdown content or error message
    """
    try:
        tool_name = "convert_to_markdown"
        arguments = {"uri": f"file:{pdf_path}"}
        
        server_params = StdioServerParameters(
            command="markitdown-mcp",
        )
        
        async with stdio_client(server_params) as (read, write):
            async with ClientSession(read, write, sampling_callback=None) as session:
                await session.initialize()
                tool_result = await session.call_tool(tool_name, arguments=arguments)
                result_content = tool_result.content[-1].text if tool_result.content else ""
                
                if not result_content.strip():
                    return "[ERROR]: No content extracted from PDF using markitdown-mcp"
                
                return result_content
                
    except Exception as e:
        return f"[ERROR]: Failed to process PDF with markitdown-mcp: {str(e)}"


async def ask_gemini_about_text(text_content: str, question: str, model_name: str = "gemini-2.5-flash") -> str:
    """
    Ask Gemini a question about text content.
    
    Args:
        text_content: The text content to ask about
        question: The question to ask
        model_name: Gemini model to use
        
    Returns:
        Gemini's response
    """
    try:
        # Use the Gemini client
        if not gemini_client:
            return "[ERROR]: Gemini client not initialized. Please check GOOGLE_API_KEY."
        
        prompt = f"""Based on the following document content, please answer this question: {question}

Try to answer the question based on the text content.
If the question is related to images in the document, try to answer the question based on context around the image.
Be confident about your answer, don't hesitate.

Document content:
{text_content}"""
        
        response = gemini_client.models.generate_content(
            model=model_name,
            contents=[prompt]  # Send prompt directly as string
        )
        
        return response.text if response.text else "[ERROR]: No response received from Gemini."
        
    except Exception as e:
        return f"[ERROR]: Failed to get response from Gemini: {str(e)}"


async def ask_gemini_about_pdf(pdf_data: bytes, question: str, model_name: str = "gemini-2.5-flash") -> str:
    """
    Ask Gemini a question about PDF content. Uses direct bytes for PDFs < 20MB,
    File API for PDFs 20-50MB.
    
    Args:
        pdf_data: Raw PDF data as bytes
        question: The question to ask
        model_name: Gemini model to use
        
    Returns:
        Gemini's response
    """
    try:
        # Use the Gemini client
        if not gemini_client:
            return "[ERROR]: Gemini client not initialized. Please check GEMINI_API_KEY."
        
        file_size = len(pdf_data)
        logger.info(f"📤 Processing PDF for Gemini (size: {file_size/1024/1024:.2f}MB)...")
        suffix = """
            When a question refers to page x of a document, please note that this refers to page x of the document's own pagination, usually starting, page number is shown in shown on the bottom of the page, not page x of the PDF file. This is because front matter like the cover, copyright page, table of contents, etc. are typically not counted in the main text pagination, 
            so page 1 of the book might correspond to page 5 or later in the PDF. 
            """
        question = question + suffix
        # Decide whether to use direct bytes or File API based on size
        if file_size <= MAX_PDF_SIZE_BYTES:
            # Use direct bytes for PDFs under 20MB
            logger.info("✅ Using direct byte processing (PDF < 20MB)")
            
            pdf_part = types.Part.from_bytes(
                data=pdf_data,
                mime_type="application/pdf"
            )
            
            response = gemini_client.models.generate_content(
                model=model_name,
                contents=[
                    pdf_part,
                    question  # Send question directly as string
                ]
            )
            
        elif file_size <= MAX_PDF_SIZE_FILE_API:
            # Use File API for PDFs between 20-50MB
            logger.info("📁 Using File API for large PDF (20-50MB)")
            
            # Create a temporary file for upload
            import tempfile
            with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp_file:
                tmp_file.write(pdf_data)
                tmp_file.flush()
                tmp_path = tmp_file.name
            
            try:
                # Upload the file using File API
                file_path = pathlib.Path(tmp_path)
                uploaded_file = gemini_client.files.upload(file=file_path)
                logger.info(f"✅ File uploaded: {uploaded_file.name}")
                
                # Generate content with the uploaded file
                response = gemini_client.models.generate_content(
                    model=model_name,
                    contents=[uploaded_file, question]
                )
                
                # Clean up the uploaded file
                try:
                    gemini_client.files.delete(name=uploaded_file.name)
                    logger.info("🧹 Cleaned up uploaded file from Gemini")
                except:
                    pass
                    
            finally:
                # Clean up temporary file
                if os.path.exists(tmp_path):
                    try:
                        os.remove(tmp_path)
                    except:
                        pass
        else:
            return f"[ERROR]: PDF too large ({file_size/1024/1024:.2f}MB). Maximum size is 50MB."
        
        return response.text if response.text else "[ERROR]: No response received from Gemini."
        
    except Exception as e:
        return f"[ERROR]: Failed to process PDF with Gemini: {str(e)}"


@mcp.tool()
async def pdf_question_answer(uri: str, question: str, model: str = "gemini-2.5-flash", max_tokens: int = 8192) -> str:
    """
    Read a PDF file from a URL or local file path and answer a question about its content using Gemini.
    
    For PDFs:
    - If size <= 20MB: Sends directly using bytes
    - If size 20-50MB and pages <= 1000: Uses File API
    - Otherwise: Converts to markdown using markitdown-mcp first, then asks Gemini
    
    Args:
        uri: The URL or local file path to the PDF. Can be:
            - HTTP/HTTPS URL (e.g., "https://example.com/document.pdf")
            - Local file path (e.g., "/path/to/document.pdf" or "document.pdf")
        question: The question to ask about the PDF content
        model: Gemini model to use (default: gemini-2.5-flash)
        max_tokens: Maximum tokens in response (not used for Gemini, kept for compatibility)
    
    Returns:
        str: Gemini's answer to the question about the PDF content
    """
    logger.info(f"📄 PDF Q&A tool called - URI: {uri[:80]}..., Question: {question[:100]}..., Model: {model}")
    start_time = time.time()
    
    # Check if Gemini client is available
    if not GOOGLE_API_KEY:
        logger.error("❌ GEMINI_API_KEY not configured")
        return "[ERROR]: GEMINI_API_KEY is not set. Please set it in your environment variables to use PDF question answering."
    
    # Validate inputs
    if not uri or not uri.strip():
        logger.error("❌ Empty URI provided")
        return "[ERROR]: URI parameter is required and cannot be empty."
    
    if not question or not question.strip():
        logger.error("❌ Empty question provided")
        return "[ERROR]: Question parameter is required and cannot be empty."
    
    temp_file_path = None
    
    try:
        # Determine if URI is a URL or local file
        is_url = uri.lower().startswith(("http://", "https://"))
        logger.info(f"📍 URI type: {'URL' if is_url else 'Local file'}")
        
        if is_url:
            # Download PDF from URL first
            try:
                logger.info("📥 Starting PDF download from URL...")
                headers = {
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
                }
                
                # Download with retries
                max_attempts = 3
                pdf_data = None
                for attempt in range(max_attempts):
                    try:
                        response = requests.get(uri, headers=headers, timeout=600)
                        response.raise_for_status()
                        pdf_data = response.content
                        break
                    except Exception as e:
                        if attempt == max_attempts - 1:
                            # Try selenium downloader as last resort
                            logger.warning(f"⚠️ Regular download failed, trying Selenium downloader: {e}")
                            print("[INFO]: Regular download failed, attempting with Selenium browser automation...")
                            
                            # Use selenium downloader
                            temp_pdf_path = tempfile.mktemp(suffix=".pdf")
                            try:
                                if download_pdf_with_selenium(uri, temp_pdf_path, timeout=120):
                                    with open(temp_pdf_path, 'rb') as f:
                                        pdf_data = f.read()
                                    logger.info("✅ Successfully downloaded PDF using Selenium")
                                    print("[INFO]: PDF downloaded successfully with Selenium")
                                else:
                                    raise Exception("Selenium download also failed")
                            finally:
                                # Clean up temp file
                                if os.path.exists(temp_pdf_path):
                                    try:
                                        os.remove(temp_pdf_path)
                                    except:
                                        pass
                            
                            if pdf_data is None:
                                raise e
                        else:
                            # Wait time: 5s, 15s for retries 1, 2
                            wait_times = [5, 15]
                            await asyncio.sleep(wait_times[attempt])
                
                if pdf_data is None:
                    raise Exception("Failed to download PDF after all retries and backup methods")
                
                logger.info(f"✅ PDF downloaded - Size: {len(pdf_data)} bytes")
                
                # Create temporary file
                suffix = ".pdf"
                temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
                temp_file.write(pdf_data)
                temp_file.flush()
                temp_file.close()
                temp_file_path = temp_file.name
                
                logger.info(f"💾 Created temporary file: {temp_file_path}")
                
                # Ensure cleanup
                def _cleanup_tempfile(path):
                    try:
                        os.remove(path)
                    except Exception:
                        pass
                atexit.register(_cleanup_tempfile, temp_file_path)
                
                # Get PDF info
                logger.info("🔍 Analyzing PDF size and page count...")
                file_size, page_count = await get_pdf_info(pdf_data)
                
                logger.info(f"📊 PDF Analysis - Size: {file_size/1024/1024:.2f}MB, Pages: {page_count}")
                print(f"[INFO]: Downloaded PDF - Size: {file_size/1024/1024:.2f}MB, Pages: {page_count}")
                
                # Check if we can send to Gemini (either direct or File API)
                if file_size <= MAX_PDF_SIZE_FILE_API and page_count <= MAX_PDF_PAGES:
                    logger.info("✅ PDF meets size/page limits for direct Gemini processing")
                    print("[INFO]: PDF meets size/page limits, sending directly to Gemini")
                    
                    # Try Gemini's direct PDF processing
                    try:
                        logger.info("🤖 Sending PDF directly to Gemini API...")
                        result = await ask_gemini_about_pdf(pdf_data, question, model)
                        
                        if "[ERROR]" not in result:
                            elapsed_time = time.time() - start_time
                            logger.info(f"✅ Direct Gemini PDF processing completed in {elapsed_time:.2f}s - Length: {len(result)} chars")
                            return result
                        else:
                            logger.warning(f"⚠️ Direct Gemini processing failed: {result}")
                            print(f"[INFO]: Direct Gemini processing failed, trying markitdown")
                            # Fall through to markitdown processing
                    
                    except Exception as gemini_error:
                        logger.warning(f"⚠️ Direct Gemini processing failed, falling back to markitdown: {gemini_error}")
                        print(f"[INFO]: Direct Gemini processing failed, trying markitdown: {gemini_error}")
                        # Fall through to markitdown processing
                else:
                    logger.info("⚠️ PDF exceeds size/page limits, using markitdown conversion")
                    print("[INFO]: PDF exceeds size/page limits, using markitdown conversion")
                
                # Use markitdown for large PDFs or if direct processing failed
                logger.info("🔄 Converting PDF to markdown using markitdown-mcp...")
                markdown_content = await process_with_markitdown(temp_file_path)
                
                if "[ERROR]" in markdown_content:
                    logger.error("❌ Markitdown conversion failed")
                    return markdown_content
                
                logger.info(f"✅ Markdown conversion completed - Length: {len(markdown_content)} chars")
                
                # Ask Gemini about the markdown content
                logger.info("🤖 Sending markdown content to Gemini for Q&A...")
                result = await ask_gemini_about_text(markdown_content, question, model)
                
                elapsed_time = time.time() - start_time
                logger.info(f"✅ PDF Q&A via markdown completed in {elapsed_time:.2f}s - Length: {len(result)} chars")
                logger.info(f"💬 Gemini response:\n{result}")
                return f"[INFO]: Processed large PDF via markdown conversion.\n\n{result}"
                
            except Exception as download_error:
                elapsed_time = time.time() - start_time
                logger.error(f"❌ PDF download/processing failed in {elapsed_time:.2f}s: {download_error}")
                return f"[ERROR]: Failed to download or process PDF from URL: {str(download_error)}"
        
        else:
            # Handle local file
            logger.info("📁 Processing local PDF file...")
            
            # Normalize file path
            if not os.path.isabs(uri):
                uri = os.path.abspath(uri)
                logger.info(f"🔄 Normalized file path: {uri}")
            
            # Check if file exists
            if not os.path.exists(uri):
                logger.error(f"❌ Local file not found: {uri}")
                return f"[ERROR]: File not found: {uri}"
            
            # Check if it's a PDF file
            if not uri.lower().endswith('.pdf'):
                logger.warning(f"⚠️ File may not be a PDF: {uri}")
                print(f"[WARNING]: File may not be a PDF (no .pdf extension): {uri}. Attempting to process anyway...")
            
            try:
                # Read the local PDF file
                logger.info(f"📖 Reading local PDF file: {uri}")
                with open(uri, "rb") as f:
                    pdf_data = f.read()
                
                logger.info(f"✅ PDF file read - Size: {len(pdf_data)} bytes")
                
                # Get PDF info
                logger.info("🔍 Analyzing local PDF size and page count...")
                file_size, page_count = await get_pdf_info(pdf_data)
                
                logger.info(f"📊 Local PDF Analysis - Size: {file_size/1024/1024:.2f}MB, Pages: {page_count}")
                print(f"[INFO]: Local PDF - Size: {file_size/1024/1024:.2f}MB, Pages: {page_count}")
                
                # Check if we can send to Gemini (either direct or File API)
                if file_size <= MAX_PDF_SIZE_FILE_API and page_count <= MAX_PDF_PAGES:
                    print("[INFO]: PDF meets size/page limits, sending directly to Gemini")
                    
                    try:
                        result = await ask_gemini_about_pdf(pdf_data, question, model)
                        
                        if "[ERROR]" not in result:
                            elapsed_time = time.time() - start_time
                            logger.info(f"✅ Direct Gemini PDF processing completed in {elapsed_time:.2f}s")
                            return result
                        else:
                            print(f"[INFO]: Direct Gemini processing failed, trying markitdown")
                            # Fall through to markitdown processing
                    
                    except Exception as gemini_error:
                        print(f"[INFO]: Direct Gemini processing failed, trying markitdown: {gemini_error}")
                        # Fall through to markitdown processing
                else:
                    print("[INFO]: PDF exceeds size/page limits, using markitdown conversion")
                
                # Use markitdown for large PDFs or if direct processing failed
                markdown_content = await process_with_markitdown(uri)
                
                if "[ERROR]" in markdown_content:
                    return markdown_content
                
                # Ask Gemini about the markdown content
                result = await ask_gemini_about_text(markdown_content, question, model)
                return f"[INFO]: Processed large PDF via markdown conversion.\n\n{result}"
                
            except FileNotFoundError:
                elapsed_time = time.time() - start_time
                logger.error(f"❌ File not found in {elapsed_time:.2f}s: {uri}")
                return f"[ERROR]: Cannot read file: {uri}. File not found."
            except PermissionError:
                elapsed_time = time.time() - start_time
                logger.error(f"❌ Permission denied in {elapsed_time:.2f}s: {uri}")
                return f"[ERROR]: Cannot read file: {uri}. Permission denied."
            except Exception as file_error:
                elapsed_time = time.time() - start_time
                logger.error(f"❌ Local PDF processing failed in {elapsed_time:.2f}s: {file_error}")
                return f"[ERROR]: Failed to process local PDF file: {str(file_error)}"
    
    except Exception as e:
        elapsed_time = time.time() - start_time
        logger.error(f"❌ Unexpected error in PDF Q&A in {elapsed_time:.2f}s: {e}")
        return f"[ERROR]: Unexpected error in pdf_question_answer: {str(e)}"
    
    finally:
        # Clean up temporary file
        if temp_file_path and os.path.exists(temp_file_path):
            try:
                logger.info(f"🧹 Cleaning up temporary file: {temp_file_path}")
                os.remove(temp_file_path)
            except Exception as cleanup_error:
                logger.warning(f"⚠️ Failed to cleanup temp file: {cleanup_error}")
                pass


@mcp.tool()
async def text_question_answer(uri: str, question: str, model: str = "gemini-2.5-flash") -> str:
    """
    Read a text or markdown file and answer a question about its content using Gemini.
    
    Args:
        uri: The URL or local file path to the text/markdown file. Can be:
            - HTTP/HTTPS URL (e.g., "https://example.com/document.txt")
            - Local file path (e.g., "/path/to/document.md" or "document.txt")
        question: The question to ask about the file content
        model: Gemini model to use (default: gemini-2.5-pro)
    
    Returns:
        str: Gemini's answer to the question about the file content
    """
    logger.info(f"📝 Text Q&A tool called - URI: {uri[:80]}..., Question: {question[:100]}..., Model: {model}")
    start_time = time.time()
    
    # Check if Gemini client is available
    if not GOOGLE_API_KEY:
        logger.error("❌ GEMINI_API_KEY not configured")
        return "[ERROR]: GEMINI_API_KEY is not set. Please set it in your environment variables to use text question answering."
    
    # Validate inputs
    if not uri or not uri.strip():
        logger.error("❌ Empty URI provided")
        return "[ERROR]: URI parameter is required and cannot be empty."
    
    if not question or not question.strip():
        logger.error("❌ Empty question provided")
        return "[ERROR]: Question parameter is required and cannot be empty."
    
    try:
        # Determine if URI is a URL or local file
        is_url = uri.lower().startswith(("http://", "https://"))
        logger.info(f"📍 URI type: {'URL' if is_url else 'Local file'}")
        
        text_content = ""
        
        if is_url:
            # Download text from URL
            try:
                logger.info("📥 Downloading text file from URL...")
                headers = {
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
                }
                
                # Download with retries
                max_attempts = 3
                text_content = None
                for attempt in range(max_attempts):
                    try:
                        response = requests.get(uri, headers=headers, timeout=600)
                        response.raise_for_status()
                        text_content = response.text
                        break
                    except Exception as e:
                        if attempt == max_attempts - 1:
                            # For text files, just raise the error (selenium is for PDFs)
                            raise e
                        # Wait time: 5s, 15s for retries 1, 2
                        wait_times = [5, 15]
                        await asyncio.sleep(wait_times[attempt])
                
                if text_content is None:
                    raise Exception("Failed to download text file after all retries")
                
                logger.info(f"✅ Text file downloaded - Length: {len(text_content)} chars")
                
            except Exception as download_error:
                logger.error(f"❌ Failed to download text file: {download_error}")
                return f"[ERROR]: Failed to download text file from URL: {str(download_error)}"
        else:
            # Handle local file
            logger.info("📁 Processing local text file...")
            
            # Normalize file path
            if not os.path.isabs(uri):
                uri = os.path.abspath(uri)
                logger.info(f"🔄 Normalized file path: {uri}")
            
            # Check if file exists
            if not os.path.exists(uri):
                logger.error(f"❌ Local file not found: {uri}")
                return f"[ERROR]: File not found: {uri}"
            
            try:
                # Read the local text file
                logger.info(f"📖 Reading local text file: {uri}")
                with open(uri, "r", encoding="utf-8") as f:
                    text_content = f.read()
                
                logger.info(f"✅ Text file read - Length: {len(text_content)} chars")
                
            except Exception as file_error:
                logger.error(f"❌ Failed to read local text file: {file_error}")
                return f"[ERROR]: Failed to read local text file: {str(file_error)}"
        
        # Ask Gemini about the text content
        logger.info("🤖 Sending text content to Gemini for Q&A...")
        result = await ask_gemini_about_text(text_content, question, model)
        
        elapsed_time = time.time() - start_time
        logger.info(f"✅ Text Q&A completed in {elapsed_time:.2f}s - Length: {len(result)} chars")
        logger.info(f"💬 Gemini response:\n{result}")
        
        return result
        
    except Exception as e:
        elapsed_time = time.time() - start_time
        logger.error(f"❌ Unexpected error in text Q&A in {elapsed_time:.2f}s: {e}")
        return f"[ERROR]: Unexpected error in text_question_answer: {str(e)}"


@mcp.tool()
async def read_file(uri: str) -> str:
    """Read various types of resources (Doc, PPT, PDF, Excel, CSV, ZIP file etc.)
    described by an file: or data: URI.

    Args:
        uri: Required. The URI of the resource to read. Need to start with 'file:' or 'data:' schemes. Files from sandbox are not supported. You should use the local file path.

    Returns:
        str: The content of the resource, or an error message if reading fails.
    """
    if not uri or not uri.strip():
        return "[ERROR]: URI parameter is required and cannot be empty."

    if "home/user" in uri:
        return "The read_file tool cannot access to sandbox file, please use the local path provided by original instruction"

    # Validate URI scheme
    valid_schemes = ["http:", "https:", "file:", "data:"]
    if not any(
        uri.lower().startswith(scheme) for scheme in valid_schemes
    ) and os.path.exists(uri):
        uri = f"file:{os.path.abspath(uri)}"

    # Validate URI scheme
    if not any(uri.lower().startswith(scheme) for scheme in valid_schemes):
        return f"[ERROR]: Invalid URI scheme. Supported schemes are: {', '.join(valid_schemes)}"

    # If it's an HTTP(S) URL, download it first with a compliant UA:
    if uri.lower().startswith(("http://", "https://")):
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }
        retry_count = 0
        data = None
        while retry_count <= 3:
            try:
                response = requests.get(uri, headers=headers, timeout=600)
                response.raise_for_status()
                data = response.content
                break  # Success, exit retry loop
            except Exception as e:
                retry_count += 1
                if retry_count > 3:
                    # Check if it's a PDF URL
                    if uri.lower().endswith('.pdf') or 'pdf' in uri.lower():
                        # Try selenium downloader for PDFs
                        logger.warning("⚠️ Regular download failed for PDF, trying Selenium downloader")
                        temp_pdf_path = tempfile.mktemp(suffix=".pdf")
                        try:
                            if download_pdf_with_selenium(uri, temp_pdf_path, timeout=120):
                                with open(temp_pdf_path, 'rb') as f:
                                    data = f.read()
                                logger.info("✅ Successfully downloaded PDF using Selenium")
                                # Continue with the rest of the function
                            else:
                                raise Exception("Selenium download failed")
                        except Exception as selenium_error:
                            # Try scrape_website tool as last resort
                            try:
                                scrape_result = await smart_request(uri)
                                return f"[INFO]: Download failed, automatically tried `scrape_website` tool instead.\n\n{scrape_result}"
                            except Exception as scrape_error:
                                return f"[ERROR]: Failed to download {uri}: {e}. Selenium failed: {selenium_error}. Also failed to scrape: {scrape_error}"
                        finally:
                            if os.path.exists(temp_pdf_path):
                                try:
                                    os.remove(temp_pdf_path)
                                except:
                                    pass
                    else:
                        # Try scrape_website tool as fallback for non-PDFs
                        try:
                            scrape_result = await smart_request(uri)
                            return f"[INFO]: Download failed, automatically tried `scrape_website` tool instead.\n\n{scrape_result}"
                        except Exception as scrape_error:
                            return f"[ERROR]: Failed to download {uri}: {e}. Also failed to scrape with `scrape_website` tool: {scrape_error}"
                await asyncio.sleep(4**retry_count)
        
        if data is None:
            return f"[ERROR]: Failed to download {uri} after all retries"

        # write to a temp file and switch URI to file:
        suffix = os.path.splitext(uri)[1] or ""
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
        tmp.write(data)
        tmp.flush()
        tmp.close()
        uri = f"file:{tmp.name}"

        # Ensure the temp file is deleted when the program exits
        def _cleanup_tempfile(path):
            try:
                os.remove(path)
            except Exception:
                pass

        atexit.register(_cleanup_tempfile, tmp.name)

    tool_name = "convert_to_markdown"
    arguments = {"uri": uri}

    server_params = StdioServerParameters(
        command="markitdown-mcp",
    )

    result_content = ""
    try:
        async with stdio_client(server_params) as (read, write):
            async with ClientSession(read, write, sampling_callback=None) as session:
                await session.initialize()
                try:
                    tool_result = await session.call_tool(
                        tool_name, arguments=arguments
                    )
                    result_content = (
                        tool_result.content[-1].text if tool_result.content else ""
                    )
                    result_content += "\n\nNote: If the document contains instructions or important information, please review them thoroughly and ensure you follow all relevant guidance."
                except Exception as tool_error:
                    return f"[ERROR]: Tool execution failed: {str(tool_error)}.\nHint: The reading tool cannot access to sandbox file, use the local path provided by original instruction instead."
    except Exception as session_error:
        return (
            f"[ERROR]: Failed to connect to markitdown-mcp server: {str(session_error)}"
        )

    return result_content


if __name__ == "__main__":
    # Set up argument parser
    parser = argparse.ArgumentParser(description="Reading MCP Server with Gemini PDF Q&A Support")
    parser.add_argument(
        "--transport",
        choices=["stdio", "http"],
        default="stdio",
        help="Transport method: 'stdio' or 'http' (default: stdio)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8080,
        help="Port to use when running with HTTP transport (default: 8080)",
    )
    parser.add_argument(
        "--path",
        type=str,
        default="/mcp",
        help="URL path to use when running with HTTP transport (default: /mcp)",
    )

    # Parse command line arguments
    args = parser.parse_args()

    # Run the server with the specified transport method
    if args.transport == "stdio":
        mcp.run(transport="stdio")
    else:
        # For HTTP transport, include port and path options
        mcp.run(transport="streamable-http", port=args.port, path=args.path)