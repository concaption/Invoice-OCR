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
from utils.seller_cloud import *

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
        today = (datetime.now()+ timedelta(days=1)).strftime("%d-%b-%Y")
        yesterday = (datetime.now() - timedelta(days=2)).strftime("%d-%b-%Y")
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

    #### Seller Cloud Integration
    try:
        logger.info("#################Starting Seller Cloud Integration###################")
        sheets_client = SheetsClient(credentials_file_path=settings.CREDENTIALS_FILE_PATH)
        drive_client = DriveClient(credentials_file_path=settings.CREDENTIALS_FILE_PATH)
        
        logger.info("Attempting to get access token - Seller Cloud")
        bearer = get_access_token()
        if bearer is None:
            raise ValueError("Failed to obtain access token - Seller Cloud")
        logger.info("Access token obtained successfully - Seller Cloud")

        logger.info("Retrieving all orders")
        data = get_all_orders(bearer)
        if data is None:
            raise ValueError("Failed to retrieve order data - Seller Cloud")
        logger.info(f"Retrieved {len(data)} orders - Seller Cloud")

        logger.info("Parsing order data - Seller Cloud")
        results = data_parse(data)
        order_data = pd.DataFrame(results, columns=['order_id', 'order_number'])
        order_data['order_id'] = order_data['order_id'].astype(str)
        logger.info(f"Parsed {len(order_data)} orders - Seller Cloud")

        try:
            logger.info(f"Adding data to Google Sheets: {settings.SPREADSHEET_NAME} - Seller Cloud")
            sheets_client.add_seller_cloud_dataframe(
                data_frame=order_data,
                sheet_name=settings.SELLER_CLOUD,
                spreadsheet_name =settings.SPREADSHEET_NAME
            )
            logger.info("Successfully added data to Google Sheets - Seller Cloud")
        except Exception as e:
            logger.error(f"Failed to add data to Google Sheets: {str(e)} - Seller Cloud")
            raise

        try:
            logger.info("Matching and updating status")
            _, to_be_uploaded = sheets_client.match_and_update_status(
                settings.SHEET_NAME, settings.SELLER_CLOUD, settings.SPREADSHEET_NAME, 'order_number', 'order_number'
            )
            logger.info(f"{len(to_be_uploaded)} items to be uploaded - Seller Cloud")
        except Exception as e:
            logger.error(f"Failed to match and update status: {str(e)} - Seller Cloud")
            raise

        for index, item in enumerate(to_be_uploaded, 1):
            try:
                logger.info(f"Processing item {index} of {len(to_be_uploaded)}")
                file_url = item.get('pdf_link')
                order_id = item.get('order_id')
                order_number = item.get('order_number')
                if not file_url or not order_id:
                    logger.warning(f"Missing file_url or order_id for item: {item} - Seller Cloud")
                    continue

                logger.info(f"Downloading and encoding file for order_id: {order_id} - Seller Cloud")

                base64_content, file_id = drive_client.download_and_encode(file_url)
                if not base64_content or not file_id:
                    logger.warning(f"Failed to download and encode file for order_id: {order_id} - Seller Cloud")
                    continue

                file_name = f"Order-NO{order_number}.pdf"
                logger.info(f"File downloaded and encoded successfully for order_id: {order_id} - Seller Cloud")

                logger.info(f"Uploading file to SellerCloud for order_id: {order_id} - Seller Cloud")
                upload_response = upload_to_sellercloud(bearer, int(order_id), base64_content, file_name)
                if upload_response == 200:
                    logger.info(f"File uploaded successfully for order_id {order_id} - Seller Cloud")
                    try:
                        sheets_client.update_column_by_identifier(
                            settings.SHEET_NAME,settings.SPREADSHEET_NAME, 'order_number', order_number, 'status', 'Uploaded')
                    except Exception as e:
                        logger.error(f"Failed to update status for order_id {order_id}: {str(e)} - Seller Cloud")
                        continue
                else:
                    logger.error(f"Failed to upload file for order_id {order_id} - Seller Cloud")

            except Exception as e:
                logger.error(f"Error processing item {index} (order_id: {order_id}): {str(e)} - Seller Cloud")
                continue

        logger.info("Order processing completed successfully - Seller Cloud")

    except Exception as e:
        logger.error(f"An error occurred during order processing: {str(e)} - Seller Cloud")
        # Handle the error appropriately (e.g., send an alert, retry, or exit)
    finally:
        logger.info("Order processing script finished execution - Seller Cloud")
        # Perform any necessary cleanup operations here
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