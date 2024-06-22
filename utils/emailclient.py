"""
path: main/emailclient.py
author: @concaption
date: 2023-10-18
description: This module contains the EmailAttachmentExtractor class for connecting to
an email inbox via IMAP4 and extracting attachments from emails.
"""

import imaplib
import email
import os
from email.header import decode_header
import traceback
import logging

logger = logging.getLogger(__name__)

class EmailAttachmentExtractor:
    """
    Class for connecting to an email inbox via IMAP4 and extracting attachments from emails.

    Attributes
    ----------
    email : str
        Email address of the account to connect to.
    password : str
        Password of the account to connect to.
    imap_server : str
        IMAP server to connect to.

    Methods
    -------
    connect()
        Connect to the IMAP server and log in.
    close_connection()
        Close the connection to the IMAP server.
    extract_pdf_attachments(directory_to_save, num_emails=5)
        Extract PDF attachments from the latest emails that have 'pdf' in their subject.
    """

    def __init__(self, email_address, password, imap_server="imap.gmail.com"):
        self.email_address = email_address
        self.password = password
        self.imap_server = imap_server
        self.mail = imaplib.IMAP4_SSL(self.imap_server)

    def connect(self):
        """
        Connect to the IMAP server and log in.

        Returns
        -------
        bool
            True if the connection was successful, False otherwise.
        """
        try:
            self.mail.login(self.email_address, self.password)
            logger.info("Successfully logged in to email account %s", self.email_address)
            return True
        except imaplib.IMAP4.error as e:
            logger.error("Login failed: %s", e)
            return False

    def close_connection(self):
        """
        Close the connection to the IMAP server.

        Returns
        -------
        None
        """
        self.mail.close()
        self.mail.logout()
        logger.info("Successfully logged out from email account %s", self.email_address)

    def extract_pdf_attachments(
        self,
        directory_to_save=None,
        num_emails=5,
        subject_contains="pdf",
        date_from=None,
        date_to=None,
    ):
        """
        Extract PDF attachments from the latest emails that have subject_contains in
        their subject and were received between date_from and date_to.

        Parameters
        ----------
        directory_to_save : str
            Directory where the attachments will be saved.
        num_emails : int
            Number of emails to process.
        subject_contains : str
            Substring to search for in the email subject.
        date_from : str
            Date in the format 'dd-mm-yyyy' to search for emails received after this date.
        date_to : str
            Date in the format 'dd-mm-yyyy' to search for emails received before this date.
        """
        try:
            # Select the mailbox to search in; 'INBOX' by default
            self.mail.select("INBOX")

            # Search for emails with pdf_contains in their subject in the mailbox and
            # were received between date_from and date_to
            criteria = []
            if subject_contains:
                criteria.append(f'SUBJECT "{subject_contains}"')
            if date_from:
                criteria.append(f"SINCE {date_from}")
            if date_to:
                criteria.append(f"BEFORE {date_to}")
            search_criteria = " ".join(criteria) if criteria else "ALL"
            logger.info("Searching emails with criteria: %s", search_criteria)

            status, messages = self.mail.search(None, search_criteria)
            if status != "OK":
                logger.error("Failed to search emails: %s", messages)
                return

            # The search returns a list of email IDs; we'll get the latest 'num_emails' emails
            messages = messages[0].split(b" ")
            if not messages or messages == [b""]:
                logger.warning(
                    "No emails found with subject containing '%s' between %s and %s", subject_contains, date_from, date_to
                )
                return

            latest_emails = messages[-num_emails:]

            pdfs = []

            for mail in latest_emails:
                # Fetch the email by ID
                status, data = self.mail.fetch(mail, "(RFC822)")
                for response_part in data:
                    if isinstance(response_part, tuple):
                        # Parse the email content
                        msg = email.message_from_bytes(response_part[1])
                        subject, encoding = decode_header(msg["Subject"])[0]
                        if isinstance(subject, bytes):
                            subject = subject.decode(encoding)
                        logger.info("Processing email subject: %s", subject)

                        # Check if the email has any attachments
                        for part in msg.walk():
                            if (
                                part.get_content_maintype() == "multipart"
                                or part.get("Content-Disposition") is None
                            ):
                                continue
                            if "attachment" in part.get("Content-Disposition"):
                                file_name = part.get_filename()
                                if file_name and file_name.endswith(".pdf"):
                                    binary_data = part.get_payload(decode=True)
                                    pdf = {
                                        "file_name": file_name,
                                        "binary_data": binary_data,
                                    }
                                    pdfs.append(pdf)
                                    logger.info("Found PDF attachment: %s", file_name)
                                    if directory_to_save:
                                        file_path = os.path.join(
                                            directory_to_save, file_name
                                        )
                                        with open(file_path, "wb") as f:
                                            f.write(binary_data)
                                        logger.info("Saved attachment: %s", file_path)
            return pdfs

        except Exception as e:
            logger.error("An error occurred: %s", e)
            traceback.print_exc()
        finally:
            self.close_connection()