"""
path: utils/scheduler.py

"""

import os
import json
import httpx
import re
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

def clean_phone_number(phone):
            if phone is not None:
                return re.sub(r'[+\-*_]', '', phone)
            return phone 

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
                                                date_from=yesterday,
                                                date_to=today
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
                        ship_from_company_name = bol.get('shipment_info', {}).get('ship_from', {}).get('company_name')
                        ship_from_contact_person = bol.get('shipment_info', {}).get('ship_from', {}).get('contact_person')
                        ship_from_contact_number = bol.get('shipment_info', {}).get('ship_from', {}).get('contact_number')
                        ship_from_address = bol.get('shipment_info', {}).get('ship_from', {}).get('address')
                        ship_to_company_name = bol.get('shipment_info', {}).get('ship_to', {}).get('company_name')
                        ship_to_contact_person = bol.get('shipment_info', {}).get('ship_to', {}).get('contact_person')
                        ship_to_contact_number = bol.get('shipment_info', {}).get('ship_to', {}).get('contact_number')
                        ship_to_address = bol.get('shipment_info', {}).get('ship_to', {}).get('address')
                        carrier_name = bol.get('shipment_info', {}).get('carrier_info', {}).get('carrier_name')
                        scac = bol.get('shipment_info', {}).get('carrier_info', {}).get('scac')
                        pro_number = bol.get('shipment_info', {}).get('carrier_info', {}).get('pro_number')
                        order_number = bol.get('shipment_info', {}).get('customer_order_information', {}).get('order_number',"")
                        shipment_id = bol.get('shipment_info', {}).get('customer_order_information', {}).get('shipment_id')
                        pallets = bol.get('shipment_info', {}).get('customer_order_information', {}).get('pallets')
                        cartons = bol.get('shipment_info', {}).get('customer_order_information', {}).get('cartons')
                        weight = bol.get('shipment_info', {}).get('customer_order_information', {}).get('weight')
                        pdf_link = bol.get('pdf_link')
                    data = [
                            {
                                'ship_from_company_name': ship_from_company_name,
                                'ship_from_contact_person': ship_from_contact_person,
                                'ship_from_contact_number': clean_phone_number(ship_from_contact_number),
                                'ship_from_address': ship_from_address,
                                'ship_to_company_name': ship_to_company_name,
                                'ship_to_contact_person': ship_to_contact_person,
                                'ship_to_contact_number': clean_phone_number(ship_to_contact_number),
                                'ship_to_address': ship_to_address,
                                'carrier_name': carrier_name,
                                'scac': scac,
                                'pro_number': pro_number,
                                'order_number': order_number,
                                'shipment_id': shipment_id,
                                'pallets': pallets,
                                'cartons': cartons,
                                'weight': weight,
                                'pdf_link': pdf_link,
                            }
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
            # email_client.close_connection()

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