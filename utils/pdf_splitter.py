import fitz
import base64
from tqdm import tqdm
import logging

logger = logging.getLogger(__name__)


def split_pdf(pdf_data):
    logger.info("Splitting PDF")
    doc = fitz.open(stream=pdf_data, filetype="pdf")
    bol_info_list = []

    for page_num in range(doc.page_count):
        page = doc.load_page(page_num)

        # Create a new PDF document for this page
        new_doc = fitz.open()
        new_doc.insert_pdf(doc, from_page=page_num, to_page=page_num)
        
        # Save the new PDF to a bytes buffer
        pdf_bytes = new_doc.write()
        new_doc.close()


         # Get the page as an image
        pix = page.get_pixmap()
        img_bytes = pix.tobytes()
        image_base64 = base64.b64encode(img_bytes).decode("utf-8")

        # Add BoL info to the list
        bol_info_list.append({
            "image": image_base64,
            "pdf": pdf_bytes
        })
    doc.close()
    logger.info("PDF Splitting complete. Found %d BoLs", len(bol_info_list))
    return bol_info_list

def process_pdf(pdf_bytes, ocr_tool, pdf_name=""):
    bol_info_list = split_pdf(pdf_bytes)
    for bol_info in tqdm(bol_info_list, desc=f"Processing BOLs from {pdf_name}"):
        page_num = bol_info_list.index(bol_info)    
        img = bol_info["image"]
        shipment_info = ocr_tool.run(img)
        if shipment_info is None:
            logger.warning("No shipment info found for BoL in %s at page %d", pdf_name, page_num)
            continue
        order_number = shipment_info.get("customer_order_information", {}).get("order_number", "")
        shipment_id = shipment_info.get("customer_order_information", {}).get("shipment_id", "")
        file_name = f"Order {order_number} - Shipment {shipment_id}.pdf"
        bol_info["shipment_info"] = shipment_info
        bol_info["file_name"] = file_name
    return bol_info_list