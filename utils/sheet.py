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
from datetime import datetime
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
        data_frame['current_datetime'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        data_frame['reviewed'] = 'FALSE'
        existing_values.dropna(how='all', inplace=True)
        existing_values.dropna(axis=1, how='all', inplace=True)
        existing_values = existing_values.astype(str)
        if append:
            if existing_values.empty:
                gd.set_with_dataframe(sheet, data_frame)
                logger.info("Appended dataframe to an empty sheet")
            else:
                existing_order_numbers = set(existing_values['order_number'].unique())
                new_order_numbers = set(data_frame['order_number'].unique())
                duplicates = existing_order_numbers.intersection(new_order_numbers)
                data_frame = data_frame[~data_frame['order_number'].isin(duplicates)]
                df_combined = pd.concat([existing_values, data_frame])
                df_combined = df_combined.astype(str)
                df_combined = df_combined.reset_index(drop=True)
                gd.set_with_dataframe(sheet, df_combined)
                logger.info("Appended dataframe to an existing sheet")    
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
    
    def add_seller_cloud_dataframe(self, sheet_name, spreadsheet_name, data_frame, append=True):
        """
        Add dataframe to sheet or append to existing data
        """
        sheet, _ = self.get_or_create_sheet(sheet_name, spreadsheet_name, obj=True)
        existing_values = gd.get_as_dataframe(sheet)
        data_frame['current_datetime'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        # data_frame = data_frame.astype(str)
        existing_values.dropna(how='all', inplace=True)
        existing_values.dropna(axis=1, how='all', inplace=True)
        existing_values = existing_values.astype(str)
        if append:
            if existing_values.empty:
                gd.set_with_dataframe(sheet, data_frame)
                logger.info("Appended dataframe to an empty sheet")
                print("Appended dataframe to an empty sheet")
            else:
                existing_order_numbers = set(existing_values['order_number'].unique())
                print(existing_order_numbers)
                new_order_numbers = set(data_frame['order_number'].unique())
                print(new_order_numbers)
                duplicates = existing_order_numbers.intersection(new_order_numbers)
                data_frame = data_frame[~data_frame['order_number'].isin(duplicates)]
                df_combined = pd.concat([existing_values, data_frame])
                df_combined = df_combined.astype(str)
                df_combined = df_combined.reset_index(drop=True)
                gd.set_with_dataframe(sheet, df_combined)
                logger.info("Appended dataframe to an existing sheet")   
        else:
            gd.set_with_dataframe(sheet, data_frame)
            logger.info("Added dataframe to an existing sheet")
        return True
    
    def match_and_update_status(self, sheet1_name, sheet2_name, spreadsheet_name, tab1_column, tab2_column):
        """
        Match and update status between two sheets based on specified columns.
        """
        matched_ids=[]
        try:
            # Fetch DataFrames for both sheets
            sheet1, _ = self.get_or_create_sheet(sheet1_name, spreadsheet_name, obj=True)
            sheet2, _ = self.get_or_create_sheet(sheet2_name, spreadsheet_name, obj=True)
            df1 = gd.get_as_dataframe(sheet1)
            df2 = gd.get_as_dataframe(sheet2)
            # Ensure the 'Status' column exists
            if 'status' not in df1.columns:
                df1['status'] = 'Not Uploaded'
            matched_ids=[]
            # Perform matching and update the 'Status' column
            for index, row in df1.iterrows():
                match = df2[df2[tab2_column] == row[tab1_column]]
                if not match.empty :
                    if not (df1.at[index, 'status'] == 'Uploaded' or df1.at[index, 'status']=='TRUE') :
                        df1.at[index, 'status'] = 'Not Uploaded'
                        matched_row = match.iloc[0]
                        matched_ids.append({
                                        'order_id': str(matched_row['order_id']).replace(".0", ""),
                                        'pdf_link': row['pdf_link'],# From df1
                                        'order_number': row['order_number']    # From df1
                                    })
                else:
                    df1.at[index, 'status'] = 'Unmatched'

            # Update the sheet with the new DataFrame
            df1 = df1.reset_index(drop=True)
            gd.set_with_dataframe(sheet1, df1)
            logger.info("Updated statuses in sheet '%s'", sheet1_name)
            return True,matched_ids

        except KeyError as e:
            logger.error(f"Error in matching: Column '{tab1_column}' or '{tab2_column}' not found: {e}")
            # return False,matched_ids
            raise
        except Exception as e:
            logger.error(f"Error in matching and updating status: {e}")
            # return False, matched_ids
            raise

    def get_dataframe_with_row_ids(self, sheet_name, spreadsheet_name):
        """
        Retrieve the sheet data as a DataFrame with row IDs.
        
        Args:
        sheet_name (str): Name of the worksheet.
        spreadsheet_name (str): Name of the spreadsheet.
        
        Returns:
        pd.DataFrame: DataFrame with an additional 'row_id' column.
        """
        sheet, _ = self.get_or_create_sheet(sheet_name, spreadsheet_name, obj=True)
        df = pd.DataFrame(sheet.get_all_records())
        df['row_id'] = range(2, len(df) + 2)  # Start from 2 to account for header row
        return df

    def update_column_by_identifier(self, sheet_name, spreadsheet_name, identifier_column, identifier_value, update_column, update_value):
        """
        Update a specific column in a row based on a unique identifier.

        Args:
        sheet_name (str): Name of the worksheet.
        spreadsheet_name (str): Name of the spreadsheet.
        identifier_column (str): Name of the column used as the unique identifier.
        identifier_value: The value to look for in the identifier column.
        update_column (str): Name of the column to update.
        update_value: The new value to set in the update_column.

        Returns:
        bool: True if update was successful, False otherwise.
        """
        try:
            df = self.get_dataframe_with_row_ids(sheet_name, spreadsheet_name)
            
            if identifier_column not in df.columns:
                raise ValueError(f"Identifier column '{identifier_column}' not found in the sheet.")

            if update_column not in df.columns:
                raise ValueError(f"Update column '{update_column}' not found in the sheet.")

            row_to_update = df[df[identifier_column] == identifier_value]
            
            if row_to_update.empty:
                logger.warning(f"No row found with {identifier_column} = {identifier_value}")
                return False

            row_id = row_to_update.iloc[0]['row_id']
            col_index = df.columns.get_loc(update_column) + 1  # +1 because gspread is 1-indexed
            
            sheet, _ = self.get_or_create_sheet(sheet_name, spreadsheet_name, obj=True)
            sheet.update_cell(row_id, col_index, update_value)

            logger.info(f"Updated '{update_column}' for row with {identifier_column} = {identifier_value}")
            return True

        except gspread.exceptions.APIError as e:
            logger.error(f"API error while updating column: {e}")
            return False
        except Exception as e:
            logger.error(f"Error updating column: {e}")
            return False