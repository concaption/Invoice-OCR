"""
path: utils/scheduler.py

"""

import os
import json
import httpx
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from datetime import datetime, timedelta

from utils.ocr import OCRTool
from utils.pdf_splitter import process_pdf


from utils.emailclient import EmailAttachmentExtractor
from utils.sheet import SheetsClient
from utils.drive import DriveClient
from app.config import settings
import logging
import pandas as pd
from tqdm import tqdm

logger = logging.getLogger(__name__)
scheduler = AsyncIOScheduler()


async def job():
    """
    Fetch email attachments from the configured email account
    """
    email_client = EmailAttachmentExtractor(
        email_address=settings.EMAIL_ADDRESS,
        password=settings.EMAIL_PASSWORD,
        imap_server=settings.IMAP_SERVER)
    if email_client.connect():
        today = datetime.now().strftime("%d-%b-%Y")
        yesterday = (datetime.now() - timedelta(days=1)).strftime("%d-%b-%Y")
        pdfs = email_client.extract_pdf_attachments(num_emails=200,
                                                subject_contains=settings.WORD_IN_SUBJECT,
                                                # date_from=yesterday,
                                                # date_to=today
                                                )               
        try:
            for pdf in tqdm(pdfs):
                result = process_pdf(pdf['binary_data'], OCRTool(), pdf['file_name'])
                
                try:
                    drive_client = DriveClient(credentials_file_path=settings.CREDENTIALS_FILE_PATH)
                    for bol in result:
                        file_name = bol.get('file_name')
                        binary_data = bol.get('pdf')
                        pdf_link = drive_client.upload_pdf(binary_data, file_name, parent_folder_id = settings.DRIVE_FOLDER_ID)
                        bol['pdf_link'] = pdf_link
                    data = [
                        {
                            'ship_from_company_name': item['shipment_info']['ship_from']['company_name'],
                            'ship_from_contact_person': item['shipment_info']['ship_from']['contact_person'],
                            'ship_from_contact_number': item['shipment_info']['ship_from']['contact_number'],
                            'ship_from_address': item['shipment_info']['ship_from']['address'],
                            'ship_to_company_name': item['shipment_info']['ship_to']['company_name'],
                            'ship_to_contact_person': item['shipment_info']['ship_to']['contact_person'],
                            'ship_to_contact_number': item['shipment_info']['ship_to']['contact_number'],
                            'ship_to_address': item['shipment_info']['ship_to']['address'],
                            'carrier_name': item['shipment_info']['carrier_info']['carrier_name'],
                            'scac': item['shipment_info']['carrier_info']['scac'],
                            'pro_number': item['shipment_info']['carrier_info']['pro_number'],
                            'order_number': item['shipment_info']['customer_order_information']['order_number'],
                            'shipment_id': item['shipment_info']['customer_order_information']['shipment_id'],
                            'pallets': item['shipment_info']['customer_order_information']['pallets'],
                            'cartons': item['shipment_info']['customer_order_information']['cartons'],
                            'weight': item['shipment_info']['customer_order_information']['weight'],
                            'pdf_link': item['pdf_link'],
                        } 
                        for item in result
                    ]

                    result_dataframe = pd.DataFrame(data)
                    sheets_client = SheetsClient(credentials_file_path=settings.CREDENTIALS_FILE_PATH)
                    sheets_client.add_dataframe(
                                        data_frame=result_dataframe,
                                        sheet_name=settings.SHEET_NAME,
                                        spreadsheet_name=settings.SPREADSHEET_NAME
                                    )
                except Exception as e:
                    logger.error(f"Error processing. Error: {e}")
                    continue

        except Exception as e:
            logger.error(f"Error processing pdf: {e}")
            email_client.disconnect()

def start():
    """
    Start the scheduler
    """
    print("Starting scheduler")
    print(settings.SCHEDULE_TIME)
    scheduler.add_job(
        job,
        trigger=CronTrigger.from_crontab(settings.SCHEDULE_TIME),
        id="fetch_email_attachments",
        name="Fetch email attachments",
        replace_existing=True
    )
    scheduler.start()
    print("Scheduler started")