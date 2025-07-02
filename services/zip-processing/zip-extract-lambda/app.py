# ------------------------------------------------------------------------------
# app.py
# ------------------------------------------------------------------------------
"""
Module: app.py
Description:
  AWS Lambda to extract PDFs from an uploaded ZIP and list them for the Map state.

Version: 1.0.3
Created: 2025-05-12
Last Modified: 2025-06-28
Modified By: Koushik Sinha
"""

import json
import logging
from common_utils import configure_logger
import io
import zipfile
import boto3
import datetime

# ─── Logging Configuration ─────────────────────────────────────────────────────
logger = configure_logger(__name__)

# Module Metadata
__author__ = "Koushik Sinha"
__version__ = "1.0.3"
__modified_by__ = "Koushik Sinha"

# Create a custom logger formatter with timestamp, level, and log message

# Initialize S3 client
s3_client: boto3.client = boto3.client('s3')


def zip_has_any_folder(zip_file_content: str) -> bool:
    """
    Check if a ZIP file contains at least one folder (directory).
    
    Args:
        zip_path (str): Path to the ZIP file.
    
    Returns:
        bool: True if the ZIP file contains at least one folder, False otherwise.
    """
    with zipfile.ZipFile(zip_file_content) as zf:
        for info in zf.infolist():
            if not info.is_dir() and "/" in info.filename:
                return True
    return False

def upload_to_s3(bucket_name: str, s3_prefix: str, local_file):
    """
    Upload a file-like object to S3 at the given prefix.
    """
    s3_client.upload_fileobj(local_file, bucket_name, s3_prefix)
    return f"s3://{bucket_name}/{s3_prefix}"

def extract_zip_file(event: dict) -> dict:
    """
    Extracts PDF files from a zip file stored in S3 and stores them in another bucket.

    Args:
        event (dict): AWS Lambda event object with the following structure:
            - `Records`: list of records containing the S3 event details
                - `body`: JSON string representing the S3 event detail

    Returns:
        dict: A dictionary containing the list of extracted PDF files' keys in the format:
            - `pdfFiles`: list of strings representing the S3 object keys of the extracted PDF files (e.g., `"s3://destination-bucket/pdf-file-1.pdf"`)
    """


    try:
        # Get the request body from the event object
        req_body: dict = json.loads(event['Records'][0]['body'])

        # Extract the source bucket name and zip file key
        req_detail: dict = req_body['detail']
        source_bucket_name: str = req_detail['bucket']['name']
        zip_file_key: str = req_detail['object']['key']
        zip_file_name: str = zip_file_key.split("/")
       
        logger.info("[getting file details from the S3]")
        # Destination bucket name
        destination_bucket_name: str = source_bucket_name
        # Read the zip file content from S3
        copy_source = {
             'Bucket': source_bucket_name,
             'Key': zip_file_key
        }
        now = datetime.datetime.now()
        date_time_folder = now.strftime('%Y/%m/%d/%H/%M/%S/')
        folder_path =  f"raw/{date_time_folder}"
        extracted_file_key = f"processed/summarization/extracted/{date_time_folder}"
        zip_file_name = zip_file_name[-1]
        destination_key = f"{folder_path}{zip_file_name}"
        zip_file_name = zip_file_name.split(".")[0]
        # Copy the object to the new location with the date structure
        s3_client.copy_object(CopySource=copy_source,Bucket=destination_bucket_name,Key=destination_key)
        
        response: dict = s3_client.get_object(Bucket=source_bucket_name, Key=destination_key)
        zip_file_content: bytes = response['Body'].read()

        pdffileList: list[str] = []
        xmlfileList: list[str] = []

        bytes_Content = io.BytesIO(zip_file_content)
        # Open the zip file using BytesIO and iterate over its contents
        has_folder = zip_has_any_folder(bytes_Content)
        with zipfile.ZipFile(bytes_Content) as zf:
         for info in zf.infolist():
            if info.is_dir():
                continue
            if info.filename.lower().endswith('.pdf') or info.filename.lower().endswith('.xml'):
                #if has_folder:
                    # Preserve folder structure in S3
                s3_key =f'{extracted_file_key}{info.filename}'
                #else:
                    # Place in a folder named after the ZIP file
                    #s3_key = f'{extracted_file_key}/{zip_file_name}/{info.filename}'
                logger.info(f"s3_key:{s3_key}")
                with zf.open(info) as file_obj:
                    uploadedFilePath = upload_to_s3(destination_bucket_name, s3_key, file_obj)
                    if info.filename.lower().endswith('.pdf'):
                        pdffileList.append({"pdffile" : uploadedFilePath})
                    if info.filename.lower().endswith('.xml'):
                        xmlfileList.append(uploadedFilePath)
            """if info.filename.lower().endswith('.xml'):
                if has_folder:
                    # Preserve folder structure in S3
                    s3_key = f'{extracted_file_key}/{info.filename}'
                else:
                    # Place in a folder named after the ZIP file
                    s3_key = f'{extracted_file_key}/{zip_file_name}/{info.filename}'
                logger.info(f"s3_key:{s3_key}")
                with zf.open(info) as file_obj:
                    xmlUploadedPath = upload_to_s3(destination_bucket_name, s3_key, file_obj)
                    xmlfileList.append(xmlUploadedPath)"""
            
        return {
            'statusCode': 200,
            'pdfFiles': pdffileList,
            'xmlFiles': xmlfileList,
            'zipFileName' :getFileName(zip_file_key)
        }

    except Exception as e:
        # Log any exceptions and return an error response
        logger.error(str(e))
        return {
            'statusCode': 500,
            'error': str(e)
        }

def getFileName(bucket_key):
    """
    Utility function to parse the S3 URI into bucket name and file key.
    """
    parts = bucket_key.split("/", 1)
    file_name = parts[1]
    return file_name

def lambda_handler(event: dict, context: dict):
    """Triggered when a ZIP file is uploaded for extraction.

    1. Unpacks PDFs from the archive and uploads them to the inbound folder for
       processing.
    2. Returns the list of extracted file keys.
    """

    result = extract_zip_file(event)
    return result
