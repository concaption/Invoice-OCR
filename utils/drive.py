"""
path: main/drive.py
author: @concaption
date: 2023-10-18
description: This module contains functions for uploading PDFs to Google Drive and 
sharing them.
"""

import logging
from oauth2client.service_account import ServiceAccountCredentials as SAC
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload,MediaIoBaseDownload
import io
import os
from urllib.parse import urlparse, parse_qs
import base64
import requests

logger = logging.getLogger(__name__)

class DriveClient:
    """
    Class for connecting to Google Drive and performing operations on it.
    """
    def __init__(self, credentials_file_path, scope=None):
        self.credentials_file_path = credentials_file_path
        self.scope = scope or [
            'https://www.googleapis.com/auth/drive',
            'https://www.googleapis.com/auth/drive.file'
        ]
        self.credentials = SAC.from_json_keyfile_name(self.credentials_file_path, self.scope)
        self.service = build('drive', 'v3', credentials=self.credentials)

    def upload_pdf(self, file_data, file_name, parent_folder_id=None):
        """
        Uploads a PDF to Google Drive and returns the file link.
        
        Args:
        - file_data: Binary data of the PDF file.
        - file_name: The full name of the file to be saved.
        - parent_folder_id: The ID of the parent folder where the file should be uploaded. (Optional)
        
        Returns:
        - The link to the uploaded PDF.
        """
        logger.info(f"Uploading file '{file_name}' to Google Drive as PDF at parent folder ID '{parent_folder_id}'...")

        file_metadata = {'name': file_name, 'mimeType': 'application/pdf', 'parents': [parent_folder_id]}
        
        media = MediaIoBaseUpload(io.BytesIO(file_data), mimetype='application/pdf')
        
        file = self.service.files().create(
            body=file_metadata,
            media_body=media,
            fields='id, webViewLink'
        ).execute()

        logger.info(f"Uploaded file '{file_name}' with file ID '{file.get('id')}'")
        logger.info(f"File link: {file.get('webViewLink')}")
        
        return file.get('webViewLink')

    def create_folders_recursively(self, folders, parent_folder_id=None):
        """
        Create folders recursively in Google Drive.
        
        Args:
        - folders: A list of folder names to be created.
        - parent_folder_id: The ID of the parent folder where the folders should be created. (Optional)
        
        Returns:
        - A list of created folder IDs.
        """
        folder_ids = []
        current_parent_id = parent_folder_id

        for folder in folders:
            folder_metadata = {
                'name': folder,
                'mimeType': 'application/vnd.google-apps.folder'
            }
            
            if current_parent_id:
                folder_metadata['parents'] = [current_parent_id]

            # Check if folder already exists
            query = f"mimeType='application/vnd.google-apps.folder' and trashed=false and name='{folder}'"
            if current_parent_id:
                query += f" and '{current_parent_id}' in parents"

            results = self.service.files().list(q=query, spaces='drive', fields='files(id, name)').execute()
            items = results.get('files', [])

            if items:
                folder_id = items[0]['id']
                logger.info(f"Folder '{folder}' already exists with ID '{folder_id}'")
            else:
                folder = self.service.files().create(body=folder_metadata, fields='id').execute()
                folder_id = folder.get('id')
                logger.info(f"Created folder '{folder}' with ID '{folder_id}'")

            folder_ids.append(folder_id)
            current_parent_id = folder_id
        
        return folder_ids

    def share_file(self, file_id, email):
        """
        Share a file with a specified email address.
        
        Args:
        - file_id: The ID of the file to be shared.
        - email: The email address to share the file with.
        
        Returns:
        - True if the operation was successful.
        """
        user_permission = {
            'type': 'user',
            'role': 'writer',
            'emailAddress': email
        }
        
        self.service.permissions().create(
            fileId=file_id,
            body=user_permission,
            fields='id'
        ).execute()
        
        logger.info(f"Shared file '{file_id}' with email '{email}'")
        
        return True
    
    def get_file_id_from_url(self, url):
        """
        Extract the file ID from a Google Drive URL.
        
        Args:
        - url: The Google Drive URL of the file.
        
        Returns:
        - The file ID if found, None otherwise.
        """
        parsed_url = urlparse(url)
        if parsed_url.hostname == 'drive.google.com' and parsed_url.path.startswith('/file/d/'):
            return parsed_url.path.split('/')[3]
        elif parsed_url.hostname == 'drive.google.com' and parsed_url.path == '/open':
            query_params = parse_qs(parsed_url.query)
            return query_params.get('id', [None])[0]
        return None

    def download_file(self, file_id):
        """
        Download a file from Google Drive using its file ID.
        
        Args:
        - file_id: The ID of the file to download.
        
        Returns:
        - The file content as bytes.
        """
        request = self.service.files().get_media(fileId=file_id)
        file = io.BytesIO()
        downloader = MediaIoBaseDownload(file, request)
        done = False
        while done is False:
            status, done = downloader.next_chunk()
            logger.info(f"Download {int(status.progress() * 100)}%.")
        return file.getvalue()

    def download_file_from_url(self, url):
        """
        Download a file from Google Drive using its URL.
        
        Args:
        - url: The Google Drive URL of the file.
        
        Returns:
        - The file content as bytes.
        """
        file_id = self.get_file_id_from_url(url)
        if not file_id:
            logger.error("Invalid Google Drive URL")
            return None
        return self.download_file(file_id)

    def file_to_base64(self, file_content):
        """
        Convert file content to a base64 encoded string.
        
        Args:
        - file_content: The content of the file as bytes.
        
        Returns:
        - Base64 encoded string of the file content.
        """
        return base64.b64encode(file_content).decode('utf-8')

    def download_and_encode(self, file_url):
        """
        Download a file from Google Drive and encode it to base64.
        
        Args:
        - file_url: The Google Drive URL of the file.
        
        Returns:
        - Base64 encoded string of the file content.
        """
        file_content = self.download_file_from_url(file_url)
        if file_content:
            return self.file_to_base64(file_content),self.get_file_id_from_url(file_url)
        return None

