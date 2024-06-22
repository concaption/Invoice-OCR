"""
path: utils/scheduler.py

"""

import os
import json
import httpx
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from datetime import datetime, timedelta

from utils.emailclient import EmailAttachmentExtractor
from utils.sheet import SheetsClient
from app.config import settings

scheduler = AsyncIOScheduler()


async def job():
    """
    Fetch email attachments from the configured email account
    """
    email_client = EmailAttachmentExtractor(
        email_address=settings.EMAIL_ADDRESS,
        password=settings.EMAIL_PASSWORD,
        imap_server=settings.IMAP_SERVER
        )
    sheets_client = SheetsClient(credentials_file_path=settings.CREDENTIALS_FILE_PATH)

    # Connect to the IMAP server and fetch the latest emails

    if email_client.connect():
        if not os.path.exists(settings.PDF_DIR):
            os.makedirs(settings.PDF_DIR)

        today = datetime.now().strftime("%d-%b-%Y")
        yesterday = (datetime.now() - timedelta(days=1)).strftime("%d-%b-%Y")
        pdfs = email_client.extract_pdf_attachments(num_emails=200,
                                            subject_contains=settings.WORD_IN_SUBJECT,
                                            date_from=yesterday,
                                            date_to=today)
        # iterate through the pdfs in tempdir and save them to Google Sheets
        for pdf_file in pdfs:

            """
            file_path = os.path.join(settings.PDF_DIR, pdf_file)
            print("Processing file: ", file_path)
            try:
                invoice = Invoice(file_path)
                order = dataframe_to_order(invoice.to_dataframe)
                data = json.loads( order.model_dump_json())
                response = httpx.post("https://iasp2.up.railway.app/items/invoice", json=data)
                if response.status_code != 200:
                    print(f"Error processing file: {file_path}")
                else:
                    print(f"File {file_path} processed successfully.")
                sheets_client.add_dataframe(
                    data_frame=invoice.to_dataframe,
                    sheet_name=settings.SHEET_NAME,
                    spreadsheet_name=settings.SPREADSHEET_NAME
                )
                print(f"Data written to Google Sheets for {pdf_file}")
            except:
                print(f"Fata Not written for {pdf_file}")
            # Delete the file from the tempdir
            os.remove(file_path)
            """

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