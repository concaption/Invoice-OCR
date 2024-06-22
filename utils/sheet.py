"""
path: main/sheet.py
author: @concaption
date: 2023-10-18
description: This module contains functions for creating, reading, updating, and
sharing Google Sheets.
"""

import time
import logging
from oauth2client.service_account import ServiceAccountCredentials as SAC
import gspread
import pandas as pd
import gspread_dataframe as gd


logger = logging.getLogger(__name__)


class SheetsClient:
    """
    Class for connecting to a Google Sheet and performing operations on it.
    """
    def __init__(self, credentials_file_path, scope=None):
        self.credentials_file_path = credentials_file_path
        self.scope = scope or [
            'https://spreadsheets.google.com/feeds',
            'https://www.googleapis.com/auth/drive'
            ]
        self.credentials = SAC.from_json_keyfile_name(self.credentials_file_path, self.scope)
        self.gc = gspread.authorize(self.credentials)

    def get_or_create_sheet(self, sheet_name, spreadsheet_name, obj=False, size='0'):
        """
        Get or create sheet
        """
        try:
            spreadsheet = self.gc.open(spreadsheet_name)
        except gspread.exceptions.SpreadsheetNotFound:
            spreadsheet = self.gc.create(spreadsheet_name)
            # Share sheet with service account email
            self.share_sheet(spreadsheet.id, "concaption@gmail.com")
        try:
            sheet = spreadsheet.worksheet(sheet_name)
        except gspread.exceptions.WorksheetNotFound:
            sheet = spreadsheet.add_worksheet(title=sheet_name, rows=size, cols=size)
        sheet_id = sheet.id
        spreadsheet_id = spreadsheet.id
        if obj:
            return sheet, spreadsheet
        return sheet_id, spreadsheet_id

    def get_sheet(self, sheet_id, spreadsheet_id):
        """
        Get sheet
        """
        spreadsheet = self.gc.open_by_key(spreadsheet_id)
        sheet = spreadsheet.get_worksheet_by_id(sheet_id)
        return sheet

    def get_sheet_values(self, sheet_id, spreadsheet_id, dataframe=True):
        """
        Get Sheet Values as a DataFrame or a list
        """
        sheet = self.get_sheet(sheet_id, spreadsheet_id)
        values = sheet.get_all_values()
        data_frame = pd.DataFrame(values[1:], columns=values[0])
        if dataframe:
            return data_frame
        return values

    def append_row(self, sheet_name, spreadsheet_name, row, timestamp=True):
        """
        Append row only if the row doesn't exist
        """
        sheet, _ = self.get_or_create_sheet(sheet_name, spreadsheet_name, obj=True)
        if timestamp:
            row.insert(0,time.strftime("%Y-%m-%d %H:%M:%S"))
        sheet.append_row(row)
        return True

    def add_dataframe(self, sheet_name, spreadsheet_name, data_frame, append=True):
        """
        Add dataframe to sheet or append to existing data
        """
        sheet, _ = self.get_or_create_sheet(sheet_name, spreadsheet_name, obj=True)
        existing_values = gd.get_as_dataframe(sheet)
        data_frame = data_frame.astype(str)
        existing_values.dropna(how='all', inplace=True)
        existing_values.dropna(axis=1, how='all', inplace=True)
        existing_values = existing_values.astype(str)
        if append:
            if existing_values.empty:
                gd.set_with_dataframe(sheet, data_frame)
                logger.info("Appended dataframe to an empty sheet")
            else:
                existing_order_numbers = set(existing_values['Order Number'].unique())
                new_order_numbers = set(data_frame['Order Number'].unique())
                duplicates = existing_order_numbers.intersection(new_order_numbers)
                
                if not duplicates:
                    df_combined = pd.concat([existing_values, data_frame])
                    df_combined = df_combined.astype(str)
                    df_combined = df_combined.reset_index(drop=True)
                    gd.set_with_dataframe(sheet, df_combined)
                    logger.info("Appended dataframe to an existing sheet")
                else:
                    logger.warning("Duplicate 'Order Number' found in the new data. Data not appended.")    
        else:
            gd.set_with_dataframe(sheet, data_frame)
            logger.info("Added dataframe to an existing sheet")
        return True

    def share_sheet(self, spreadsheet_id, email):
        """
        Share sheet with email
        """
        sh = self.gc.open_by_key(key=spreadsheet_id)
        sh.share(email, perm_type='user', role='writer')
        return True