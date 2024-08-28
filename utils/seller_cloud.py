import requests
import os
from dotenv import load_dotenv
from oauth2client.service_account import ServiceAccountCredentials as SAC
import pandas as pd
import logging




logger = logging.getLogger(__name__)
load_dotenv()


def get_access_token():
    url = 'https://cvi.api.sellercloud.com/rest/api/token'
    data = {
        "Username": os.getenv('SELLER_EMAIL_ADDRESS'),
        "Password": os.getenv('SELLER_PWD')
    }
    try:
        response = requests.post(url, json=data)
    except:
        return None

    if response.status_code == 200:
        token = response.json()
        return token['access_token']
    else:
        return None


def get_all_orders(api_token):
    url = 'https://cvi.api.sellercloud.com/rest/api/Orders?model.updatedFromDateRange=9'
    headers = {
        'Authorization': f'Bearer {api_token}',
        'Content-Type': 'application/json'
    }
    try:
        response = requests.get(url, headers=headers)
    except:
        return None

    if response.status_code == 200:
        data = response.json()
        return data
    else:
        return None


def data_parse(orders):
    # Extract the ID and OrderSourceOrderID for each item
    try:
        result = [(item["ID"], item["OrderSourceOrderID"].replace("-Sample", "") if item["OrderSourceOrderID"] else "Missing") for item in orders["Items"]]
    except:
        return None
    return result


def upload_to_sellercloud(api_key,order_id, file_content, file_name):
    url = f"https://cvi.api.sellercloud.com/rest/api/Orders/{order_id}/UploadDocument"
    headers = {
        "accept": "application/json",
        "content-type": "application/json",
        "Authorization": f"Bearer {api_key}"
    }
    payload = {
        "fileName": file_name,
        "fileContent": file_content
    }
    response = requests.post(url, headers=headers, json=payload)
    return response.status_code